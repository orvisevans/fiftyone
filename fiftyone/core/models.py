"""
FiftyOne models.

| Copyright 2017-2020, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""
import logging
import numpy as np

import eta.core.image as etai
import eta.core.learning as etal
import eta.core.models as etam
import eta.core.utils as etau
import eta.core.video as etav
import eta.core.web as etaw

import fiftyone.core.media as fom
import fiftyone.core.utils as fou


logger = logging.getLogger(__name__)


def apply_model(samples, model, label_field, confidence_thresh=None):
    """Applies the :class:`Model` to the samples in the collection.

    Args:
        samples: a :class:`fiftyone.core.collections.SampleCollection`
        model: a :class:`Model`
        label_field: the name (or prefix) of the field in which to store the
            model predictions
        confidence_thresh (None): an optional confidence threshold to apply to
            any applicable labels generated by the model
    """
    if samples.media_type == fom.VIDEO:
        _apply_video_model(samples, model, label_field, confidence_thresh)
    else:
        _apply_image_model(samples, model, label_field, confidence_thresh)


def _apply_image_model(samples, model, label_field, confidence_thresh):
    # Use data loaders for Torch models, if possible
    if isinstance(model, TorchModelMixin):
        # Local import to avoid unnecessary Torch dependency
        import fiftyone.utils.torch as fout

        fout.apply_torch_image_model(
            samples, model, label_field, confidence_thresh=confidence_thresh
        )
        return

    with model:
        with fou.ProgressBar() as pb:
            for sample in pb(samples):
                # Perform prediction
                img = etai.read(sample.filepath)
                label = model.predict(img)

                # Save labels
                sample.add_labels(
                    label, label_field, confidence_thresh=confidence_thresh
                )


def _apply_video_model(samples, model, label_field, confidence_thresh):
    with model:
        with fou.ProgressBar() as pb:
            for sample in pb(samples):
                # Perform prediction
                with etav.FFmpegVideoReader(sample.filepath) as video_reader:
                    label = model.predict(video_reader)

                # Save labels
                sample.add_labels(
                    label, label_field, confidence_thresh=confidence_thresh
                )


def build_model(model_config_dict, model_path=None, **kwargs):
    """Builds the model specified by the given :class:`ModelConfig` dict.

    Args:
        model_config_dict: a :class:`ModelConfig` dict
        model_path (None): an optional model path to inject into the
            ``model_path`` field of the model's ``Config`` instance, which must
            implement the ``eta.core.learning.HasPublishedModel`` interface.
            This is useful when working with a model whose weights are stored
            locally and do not need to be downloaded
        **kwargs: optional keyword arguments to inject into the model's
            ``Config`` instance

    Returns:
        a :class:`Model` instance
    """
    import fiftyone.core.eta_utils as foe

    # Inject config args
    if kwargs:
        if model_config_dict["type"] == etau.get_class_name(foe.ETAModel):
            _merge_config(model_config_dict["config"]["config"], kwargs)
        else:
            _merge_config(model_config_dict["config"], kwargs)

    # Load model config
    config = ModelConfig.from_dict(model_config_dict)

    #
    # Inject model path
    #
    # Models must be implemented in one of the following ways in order for
    # us to know how to inject ``model_path``:
    #
    # (1) Their config implements ``eta.core.learning.HasPublishedModel``
    #
    # (2) Their config is an ``fiftyone.core.eta_utils.ETAModelConfig`` whose
    #     embedded config implements ``eta.core.learning.HasPublishedModel``
    #
    if model_path:
        if isinstance(config.config, etal.HasPublishedModel):
            config.config.model_name = None
            config.config.model_path = model_path
        elif isinstance(config.config, foe.ETAModelConfig) and isinstance(
            config.config.config, etal.HasPublishedModel
        ):
            config.config.config.model_name = None
            config.config.config.model_path = model_path
        else:
            raise ValueError(
                "Model config must implement the %s interface"
                % etal.HasPublishedModel
            )

    # Build model
    return config.build()


def _merge_config(d, kwargs):
    for k, v in kwargs.items():
        if k in d and isinstance(d[k], dict):
            d[k].update(v)
        else:
            d[k] = v


class ModelConfig(etal.ModelConfig):
    """Base configuration class that encapsulates the name of a :class:`Model`
    and an instance of its associated Config class.

    Args:
        type: the fully-qualified class name of the :class:`Model` subclass
        config: an instance of the Config class associated with the model
    """

    pass


class Model(etal.Model):
    """Abstract base class for models.

    This class declares the following conventions:

    (a)     :meth:`Model.__init__` should take a single ``config`` argument
            that is an instance of ``<Model>Config``

    (b)     Models implement the context manager interface. This means that
            models can optionally use context to perform any necessary setup
            and teardown, and so any code that builds a model should use the
            ``with`` syntax
    """

    def predict(self, arg):
        """Peforms prediction on the given data.

        Image models should support, at minimum, processing ``arg`` values that
        are uint8 numpy arrays (HWC).

        Video models should support, at minimum, processing ``arg`` values that
        are ``eta.core.video.VideoReader`` instances.

        Args:
            arg: the data

        Returns:
            a :class:`fiftyone.core.labels.Label` instance or dict of
            :class:`fiftyone.core.labels.Label` instances containing the
            predictions
        """
        raise NotImplementedError("subclasses must implement predict()")

    def predict_all(self, args):
        """Performs prediction on the given iterable of data.

        Image models should support, at minimum, processing ``args`` values
        that are uint8 numpy arrays (NHWC).

        Video models should support, at minimum, processing ``args`` values
        that are lists of ``eta.core.video.VideoReader`` instances.

        Subclasses can override this method to increase efficiency, but, by
        default, this method simply iterates over the data and applies
        :meth:`predict` to each.

        Args:
            args: an iterable of data

        Returns:
            a list of :class:`fiftyone.core.labels.Label` instances or a list
            of dicts of :class:`fiftyone.core.labels.Label` instances
            containing the predictions
        """
        return [self.predict(arg) for arg in args]


class EmbeddingsMixin(object):
    """Mixin for :class:`Model` classes that can generate embeddings for
    their predictions.

    This mixin allows for the possibility that only some instances of a class
    are capable of generating embeddings, per the value of the
    :meth:`has_embeddings` property.
    """

    @property
    def has_embeddings(self):
        """Whether this instance has embeddings."""
        raise NotImplementedError("subclasses must implement has_embeddings")

    def get_embeddings(self):
        """Returns the embeddings generated by the last forward pass of the
        model.

        By convention, this method should always return an array whose first
        axis represents batch size (which will always be 1 when :meth:`predict`
        was last used).

        Returns:
            a numpy array containing the embedding(s)
        """
        raise NotImplementedError("subclasses must implement get_embeddings()")

    def embed(self, arg):
        """Generates an embedding for the given data.

        Subclasses can override this method to increase efficiency, but, by
        default, this method simply calls :meth:`predict` and then returns
        :meth:`get_embeddings`.

        Args:
            arg: the data. See :meth:`predict` for details

        Returns:
            a numpy array containing the embedding
        """
        # pylint: disable=no-member
        self.predict(arg)
        return self.get_embeddings()

    def embed_all(self, args):
        """Generates embeddings for the given iterable of data.

        Subclasses can override this method to increase efficiency, but, by
        default, this method simply iterates over the data and applies
        :meth:`embed` to each.

        Args:
            args: an iterable of data. See :meth:`predict_all` for details

        Returns:
            a numpy array containing the embeddings stacked along axis 0
        """
        return np.stack([self.embed(arg) for arg in args], axis=0)


class TorchModelMixin(object):
    """Mixin for :class:`Model` classes that support feeding data for inference
    via a ``torch.utils.data.DataLoader``.
    """

    @property
    def batch_size(self):
        """The recommended batch size to use when feeding data to the model,
        or ``None`` if batching is not supported.
        """
        raise NotImplementedError("subclasses must implement batch_size")

    @property
    def transforms(self):
        """The ``torchvision.transforms`` that will/must be applied to each
        input before prediction.
        """
        raise NotImplementedError("subclasses must implement transforms")


class ModelManagerConfig(etam.ModelManagerConfig):
    """Config settings for a :class:`ModelManager`.

    Args:
        url (None): the URL of the file
        google_drive_id (None): the ID of the file in Google Drive
        extract_archive (None): whether to extract the downloaded model, which
            is assumed to be an archive
        delete_archive (None): whether to delete the archive after extracting
            it, if applicable
    """

    def __init__(self, d):
        super().__init__(d)

        self.url = self.parse_string(d, "url", default=None)
        self.google_drive_id = self.parse_string(
            d, "google_drive_id", default=None
        )


class ModelManager(etam.ModelManager):
    """Class for downloading public FiftyOne models."""

    @staticmethod
    def upload_model(model_path, *args, **kwargs):
        raise NotImplementedError("Uploading models via API is not supported")

    def _download_model(self, model_path):
        if self.config.google_drive_id:
            gid = self.config.google_drive_id
            logger.info("Downloading model from Google Drive ID '%s'...", gid)
            etaw.download_google_drive_file(gid, path=model_path)
        elif self.config.url:
            url = self.config.url
            logger.info("Downloading model from '%s'...", url)
            etaw.download_file(url, path=model_path)
        else:
            raise ValueError(
                "Invalid ModelManagerConfig '%s'" % str(self.config)
            )

    def delete_model(self):
        raise NotImplementedError("Deleting models via API is not supported")
