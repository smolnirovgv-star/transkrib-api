"""Pause-based phrase segmentation from Whisper segments."""

import logging

logger = logging.getLogger("video_processor.pause_detector")

PAUSE_THRESHOLD = 0.8  # seconds


def detect_pauses(segments: list[dict], pause_threshold: float = PAUSE_THRESHOLD) -> list[dict]:
    """
    Augment Whisper raw segments with pause_before field.
    Input:  [{text, start, end}, ...]
    Output: [{text, start, end, pause_before}, ...]
    """
    result = []
    for i, seg in enumerate(segments):
        pause_before = 0.0
        if i > 0:
            gap = seg["start"] - segments[i - 1]["end"]
            if gap > pause_threshold:
                pause_before = round(gap, 2)
        result.append({
            "text": seg["text"],
            "start": seg["start"],
            "end": seg["end"],
            "pause_before": pause_before,
        })
    logger.debug(f"detect_pauses: {len(result)} phrases, {sum(1 for p in result if p['pause_before'] > 0)} pauses")
    return result
