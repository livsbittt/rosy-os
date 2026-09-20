"""Subject: lane following — floor line to lateral error plus loss tracking.

A lane is a bright line on a dark floor. Detection is threshold plus column
centroid — no model, no YOLO (SRS NAV-007). The tracker turns the observation
stream into TRACKING/LOST: loss beyond the grace period demands stop, never a
blind search drive. ROS-free, same contract onboard and in fixtures.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np


#: NAV-007 lane crawl cap. A separate mode cap, not the SAF-004 profile cap.
LANE_MAX_LINEAR_M_S = 0.10

#: Loss grace before stop is demanded (SRS NAV-007: 3 s).
LANE_LOST_GRACE_S = 3.0

_BRIGHT = 180
_WASHED_FRACTION = 0.40


@dataclass(frozen=True)
class LaneObservation:
    """Lateral error in [-1, 1]: 0 centred, positive means the lane is right
    of centre (steer right)."""

    error: float
    confidence: float


def detect_lane_error(bgr: np.ndarray) -> LaneObservation | None:
    """Find the lane centroid in the bottom band, or None when there is no
    lane to follow. A washed-out frame (lights on full white) is also None —
    driving on would be a guess, not tracking."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    band = gray[int(gray.shape[0] * 0.4):, :]
    _, bright = cv2.threshold(band, _BRIGHT, 255, cv2.THRESH_BINARY)
    lit = (bright > 0).sum()
    if lit <= 0:
        return None
    if lit > _WASHED_FRACTION * band.size:
        return None
    column = bright.sum(axis=0).astype(np.float64)
    total = float(column.sum())
    width = float(band.shape[1])
    centroid = float((column * np.arange(band.shape[1])).sum() / total)
    error = max(-1.0, min(1.0, (centroid - width / 2.0) / (width / 2.0)))
    confidence = min(1.0, float(lit) / 1500.0)
    if confidence <= 0.0:
        return None
    return LaneObservation(error=error, confidence=confidence)


class LaneTracker:
    """Loss accounting. `update` feeds observations (None = missed frame);
    `stop_demanded` fires once the gap outlasts the grace period."""

    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 lost_grace_s: float = LANE_LOST_GRACE_S) -> None:
        self._clock = clock
        self._grace = float(lost_grace_s)
        self.state = "IDLE"
        self._last_seen: float | None = None

    def update(self, observation: LaneObservation | None, at: float | None = None) -> None:
        now = self._clock() if at is None else at
        if observation is None:
            return
        self._last_seen = now
        self.state = "TRACKING"

    def stop_demanded(self, at: float | None = None) -> bool:
        if self._last_seen is None:
            return False
        now = self._clock() if at is None else at
        if now - self._last_seen > self._grace:
            self.state = "LOST"
            return True
        return False
