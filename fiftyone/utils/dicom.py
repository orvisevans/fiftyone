"""
DICOM utilities.

| Copyright 2017-2021, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""
import logging
import os
import warnings

import numpy as np

import eta.core.utils as etau

import fiftyone.utils.data as foud
import fiftyone.core.utils as fou

fou.ensure_package("pydicom")
import pydicom
from pydicom.fileset import FileInstance, FileSet


logger = logging.getLogger(__name__)


class DICOMSampleParser(foud.LabeledImageSampleParser):
    """Parser for labeled image samples stored in
    `DICOM format <https://en.wikipedia.org/wiki/DICOM>`_.

    Args:
        keywords (None): an optional keyword or list of keywords from
            :meth:`pydicom:pydicom.dataset.Dataset.dir` to load from the DICOM
            files. By default, all available fields are loaded
        parsers (None): an optional dict mapping keywords to functions that
            parse the values generated by
            :meth:`pydicom:pydicom.dataset.Dataset.get` for certain fields. By
            default, all fields are converted to primitive values, if possible
    """

    def __init__(self, keywords=None, parsers=None):
        if etau.is_str(keywords):
            keywords = [keywords]

        super().__init__()

        self.keywords = keywords
        self.parsers = parsers
        self._ds = None

    @property
    def label_cls(self):
        return None

    @property
    def has_image_path(self):
        return False

    @property
    def has_image_metadata(self):
        return False

    def get_image(self):
        self._ensure_ds()
        return _get_image(self._ds)

    def get_label(self):
        self._ensure_ds()

        if self.keywords is not None:
            fields = self.keywords
            blacklist = set()
        else:
            fields = self._ds.dir()
            blacklist = {"PixelData", "DataSetTrailingPadding"}

        label = {}

        for kw in fields:
            if kw in blacklist:
                continue

            value = self._ds.get(kw, default=None)

            if self.parsers is not None and kw in self.parsers:
                parser = self.parsers[kw]
                value = parser(value)

            if value is None:
                continue

            _value, success = _to_python(value)

            if not success:
                msg = "Ignoring field '%s' with unsupported type %s" % (
                    kw,
                    type(value),
                )
                warnings.warn(msg)
                continue

            label[kw] = _value

        return label

    def clear_sample(self):
        super().clear_sample()
        self._ds = None

    def _ensure_ds(self):
        if self._ds is None:
            if isinstance(self.current_sample, FileInstance):
                self._ds = self.current_sample.load()
            else:
                self._ds = pydicom.dcmread(self.current_sample)


class DICOMDatasetImporter(
    foud.LabeledImageDatasetImporter, foud.ImportPathsMixin
):
    """Importer for DICOM datasets datasets stored on disk.

    See :ref:`this page <DICOMDataset-import>` for format details.

    Args:
        dataset_dir (None): the dataset directory
        images_dir (None): the directory in which the images will be written.
            If not provided, the images will be unpacked into ``dataset_dir``
        dicom_path (None): an optional parameter that enables explicit control
            over the location of the DICOM files. Can be any of the following:

            -   a glob pattern like ``"*.dcm"`` specifying the location of the
                DICOM files in ``dataset_dir``
            -   the name of a DICOMDIR file in ``dataset_dir``
            -   an absolute glob pattern of DICOM files or the absolute path to
                a DICOMDIR file. In this case, ``dataset_dir`` has no effect

            If None, the parameter will default to ``*.dcm``
        keywords (None): an optional keyword or list of keywords from
            :meth:`pydicom:pydicom.dataset.Dataset.dir` to load from the DICOM
            files. By default, all available fields are loaded
        parsers (None): an optional dict mapping keywords to functions that
            parse the values generated by
            :meth:`pydicom:pydicom.dataset.Dataset.get` for certain fields. By
            default, all fields are converted to primitive values, if possible
        image_format (None): the image format to use to write the images to
            disk. By default, ``fiftyone.config.default_image_ext`` is used
        shuffle (False): whether to randomly shuffle the order in which the
            samples are imported
        seed (None): a random seed to use when shuffling
        max_samples (None): a maximum number of samples to import. By default,
            all samples are imported
    """

    def __init__(
        self,
        dataset_dir=None,
        images_dir=None,
        dicom_path=None,
        keywords=None,
        parsers=None,
        image_format=None,
        shuffle=False,
        seed=None,
        max_samples=None,
    ):
        if dataset_dir is None and dicom_path is None:
            raise ValueError(
                "At least one of `dataset_dir` and `dicom_path` must be "
                "provided"
            )

        dicom_path = self._parse_labels_path(
            dataset_dir=dataset_dir, labels_path=dicom_path, default="*.dcm",
        )

        if images_dir is None:
            images_dir = os.path.abspath(os.path.dirname(dicom_path))
            logger.warning(
                "No `images_dir` provided. Images will be unpacked to '%s'",
                images_dir,
            )

        super().__init__(
            dataset_dir=dataset_dir,
            shuffle=shuffle,
            seed=seed,
            max_samples=max_samples,
        )

        self.dicom_path = dicom_path
        self.images_dir = images_dir
        self.keywords = keywords
        self.parsers = parsers
        self.image_format = image_format

        self._sample_parser = DICOMSampleParser(
            keywords=keywords, parsers=parsers
        )
        self._dataset_ingestor = None
        self._iter_dataset_ingestor = None
        self._num_samples = None

    def __len__(self):
        return self._num_samples

    def __iter__(self):
        self._iter_dataset_ingestor = iter(self._dataset_ingestor)
        return self

    def __next__(self):
        return next(self._iter_dataset_ingestor)

    @property
    def label_cls(self):
        return None

    @property
    def has_dataset_info(self):
        return False

    @property
    def has_image_metadata(self):
        return self._sample_parser.has_image_metadata

    def setup(self):
        if os.path.isfile(self.dicom_path):
            if not os.path.splitext(self.dicom_path)[1]:
                # DICOMDIR file
                ds = pydicom.dcmread(self.dicom_path)
                samples = list(FileSet(ds))
            else:
                # Single DICOM file
                samples = [self.dicom_path]
        else:
            # Glob pattern of DICOM files
            samples = etau.get_glob_matches(self.dicom_path)

        samples = self._preprocess_list(samples)
        self._num_samples = len(samples)

        self._dataset_ingestor = foud.LabeledImageDatasetIngestor(
            self.images_dir,
            samples,
            self._sample_parser,
            image_format=self.image_format,
        )
        self._dataset_ingestor.setup()

    def close(self, *args):
        self._dataset_ingestor.close(*args)


def _get_image(ds):
    # @todo allow non 8-bit images here?

    img = ds.pixel_array

    low = ds.get("SmallestImagePixelValue", 0)
    high = ds.get("LargestImagePixelValue", None)
    if high is None:
        high = img.max()

    return ((255 / max(high - low, 1)) * (img - low)).astype(np.uint8)


def _to_python(value):
    vtype = type(value)

    if issubclass(vtype, _LIST_TYPES):
        ctype = value.type_constructor

        if ctype in _PRIMITIVE_TYPES:
            return [ctype(v) for v in value], True

        ctype = _SCALAR_FIELD_TYPES_MAP.get(ctype, None)
        if ctype is not None:
            return [ctype(v) for v in value], True

        return None, False

    if vtype in _PRIMITIVE_TYPES:
        return value, True

    vtype = _SCALAR_FIELD_TYPES_MAP.get(vtype, None)
    if vtype is not None:
        return vtype(value), True

    return None, False


_PRIMITIVE_TYPES = (int, float, str, list)
_LIST_TYPES = (pydicom.multival.MultiValue,)

_SCALAR_FIELD_TYPES_MAP = {
    # pydicom.valuerep.DA: datetime.date,
    # pydicom.valuerep.DT: datetime.datetime,
    pydicom.valuerep.DSfloat: float,
    pydicom.valuerep.DSdecimal: float,
    pydicom.valuerep.IS: int,
    pydicom.valuerep.PersonName: str,
    pydicom.valuerep.PersonNameUnicode: str,
    pydicom.uid.UID: str,
}
