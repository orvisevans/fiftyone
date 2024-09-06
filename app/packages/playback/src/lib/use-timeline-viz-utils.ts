import { useSetAtom } from "jotai";
import React from "react";
import { GLOBAL_TIMELINE_ID } from "./constants";
import { setFrameNumberAtom, TimelineName } from "./state";
import { useTimeline } from "./use-timeline";

/**
 * This hook provides access to some utilties that could be used
 * to render a visualization of the timeline.
 *
 *
 * @param name - The name of the timeline to access. Defaults to the global timeline
 * scoped to the current modal.
 */
export const useTimelineVizUtils = (
  name: TimelineName = GLOBAL_TIMELINE_ID
) => {
  const { config, frameNumber, pause } = useTimeline(name);
  const setFrameNumber = useSetAtom(setFrameNumberAtom);

  const getSeekValue = React.useCallback(() => {
    // offset by -1 since frame indexing is 1-based
    const numerator = frameNumber - 1;
    const denominator = config.totalFrames - 1;
    return (numerator / denominator) * 100;
  }, [frameNumber]);

  const seekTo = React.useCallback((newSeekValue: number) => {
    pause();
    const newFrameNumber = Math.ceil((newSeekValue / 100) * config.totalFrames);
    setFrameNumber({ name, newFrameNumber });
  }, []);

  return {
    getSeekValue,
    seekTo,
  };
};