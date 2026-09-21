"""ROS-free camera evidence for semantic road markings and traffic signals.

Semantic truth from the simulation scene is deliberately not an input here.
The detector sees only the BGR camera frame and an optional, independently
validated ground-plane model used for metric range.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from .lane import LaneObservation


@dataclass(frozen=True)
class RoadPerceptionConfig:
    bright_threshold: int = 180
    lane_roi_top_fraction: float = 0.30
    horizontal_min_fraction: float = 0.40
    horizontal_padding_px: int = 2
    crosswalk_min_bars: int = 3
    crosswalk_max_gap_px: int = 20
    signal_roi_bottom_fraction: float = 0.35
    signal_min_pixels: int = 50


@dataclass(frozen=True)
class RoadMarkingObservation:
    image_row: float
    distance_m: float | None
    confidence: float


@dataclass(frozen=True)
class TrafficSignalObservation:
    colour: str
    confidence: float


@dataclass(frozen=True)
class RoadObservation:
    lane: LaneObservation | None
    stop_line: RoadMarkingObservation | None
    crosswalk: RoadMarkingObservation | None
    signal: TrafficSignalObservation | None
    signal_conflict: bool = False


def _groups(flags: np.ndarray) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(flags)
    if indexes.size == 0:
        return []
    result = []
    start = previous = int(indexes[0])
    for raw in indexes[1:]:
        current = int(raw)
        if current != previous + 1:
            result.append((start, previous))
            start = current
        previous = current
    result.append((start, previous))
    return result


def _crosswalk_cluster(groups: list[tuple[int, int]], max_gap: int,
                       minimum: int) -> list[int]:
    """Return indexes of the largest regularly nearby horizontal cluster."""
    best: list[int] = []
    current: list[int] = []
    previous = None
    for index, (top, bottom) in enumerate(groups):
        centre = (top + bottom) / 2.0
        if previous is None or centre - previous <= max_gap:
            current.append(index)
        else:
            if len(current) > len(best):
                best = current
            current = [index]
        previous = centre
    if len(current) > len(best):
        best = current
    return best if len(best) >= minimum else []


def _ground_distance(ground, row: float, column: float) -> float | None:
    if ground is None:
        return None
    try:
        value = ground.distance(row, column)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or value < 0.0):
        return None
    return float(value)


def _marking(group_indexes: list[int], groups: list[tuple[int, int]],
             bright: np.ndarray, ground) -> RoadMarkingObservation | None:
    if not group_indexes:
        return None
    selected = [groups[index] for index in group_indexes]
    row = float(max((top + bottom) / 2.0 for top, bottom in selected))
    pixels = sum(int((bright[top:bottom + 1] > 0).sum())
                 for top, bottom in selected)
    capacity = max(1, sum(bottom - top + 1 for top, bottom in selected)
                   * bright.shape[1])
    return RoadMarkingObservation(
        image_row=row,
        distance_m=_ground_distance(ground, row, bright.shape[1] / 2.0),
        confidence=min(1.0, pixels / capacity),
    )


def _lane(bright: np.ndarray, horizontal_groups: list[tuple[int, int]],
          config: RoadPerceptionConfig) -> LaneObservation | None:
    masked = bright.copy()
    for top, bottom in horizontal_groups:
        start = max(0, top - config.horizontal_padding_px)
        end = min(masked.shape[0], bottom + config.horizontal_padding_px + 1)
        masked[start:end, :] = 0
    roi_top = int(masked.shape[0] * config.lane_roi_top_fraction)
    band = masked[roi_top:, :]
    lit = int((band > 0).sum())
    if lit == 0 or lit > band.size * 0.40:
        return None
    column = band.sum(axis=0).astype(np.float64)
    total = float(column.sum())
    if total <= 0.0:
        return None
    width = float(band.shape[1])
    centroid = float((column * np.arange(band.shape[1])).sum() / total)
    error = max(-1.0, min(1.0, (centroid - width / 2.0) / (width / 2.0)))
    confidence = min(1.0, lit / max(1.0, band.shape[0] * 8.0))
    return LaneObservation(error=error, confidence=confidence)


def _signal(bgr: np.ndarray, config: RoadPerceptionConfig):
    bottom = max(1, int(bgr.shape[0] * config.signal_roi_bottom_fraction))
    hsv = cv2.cvtColor(bgr[:bottom], cv2.COLOR_BGR2HSV)
    masks = {
        "RED": (cv2.inRange(hsv, (0, 120, 100), (10, 255, 255))
                | cv2.inRange(hsv, (170, 120, 100), (179, 255, 255))),
        "YELLOW": cv2.inRange(hsv, (18, 120, 100), (38, 255, 255)),
        "GREEN": cv2.inRange(hsv, (40, 100, 80), (90, 255, 255)),
    }
    counts = {colour: int((mask > 0).sum()) for colour, mask in masks.items()}
    active = [colour for colour, count in counts.items()
              if count >= config.signal_min_pixels]
    if len(active) > 1:
        return None, True
    if not active:
        return None, False
    colour = active[0]
    confidence = min(
        1.0, counts[colour] / max(1.0, config.signal_min_pixels * 2.0))
    observation = TrafficSignalObservation(
        colour=colour, confidence=confidence)
    return observation, False


def detect_road_observation(bgr: np.ndarray, *, ground=None,
                            config: RoadPerceptionConfig | None = None
                            ) -> RoadObservation:
    """Detect road markings and signal from a processed BGR frame."""
    if not isinstance(bgr, np.ndarray) or bgr.ndim != 3 or bgr.shape[2] != 3 \
            or bgr.size == 0:
        raise ValueError("road camera frame must be a non-empty BGR array")
    config = config or RoadPerceptionConfig()
    if not 1 <= config.bright_threshold <= 254:
        raise ValueError("bright_threshold must be in [1, 254]")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(
        gray, config.bright_threshold, 255, cv2.THRESH_BINARY)
    row_fraction = (bright > 0).mean(axis=1)
    horizontal_groups = _groups(row_fraction >= config.horizontal_min_fraction)
    crosswalk_indexes = _crosswalk_cluster(
        horizontal_groups,
        config.crosswalk_max_gap_px,
        config.crosswalk_min_bars,
    )
    crosswalk_set = set(crosswalk_indexes)
    stop_indexes = [index for index in range(len(horizontal_groups))
                    if index not in crosswalk_set]
    # A single stop-line verdict is the closest independent horizontal mark.
    stop_indexes = stop_indexes[-1:] if stop_indexes else []
    signal, conflict = _signal(bgr, config)
    return RoadObservation(
        lane=_lane(bright, horizontal_groups, config),
        stop_line=_marking(stop_indexes, horizontal_groups, bright, ground),
        crosswalk=_marking(
            crosswalk_indexes, horizontal_groups, bright, ground),
        signal=signal,
        signal_conflict=conflict,
    )


def _marking_payload(observation: RoadMarkingObservation | None) -> dict:
    return {
        "visible": observation is not None,
        "image_row": (
            None if observation is None else float(observation.image_row)),
        "distance_m": None if observation is None else observation.distance_m,
        "confidence": (
            0.0 if observation is None else float(observation.confidence)),
    }


def road_observation_payload(source: str, stamp: float, map_id: str,
                             scene_revision: str,
                             observation: RoadObservation) -> dict:
    """Build revision-bound JSON evidence for CORE's traffic policy."""
    if source != "CAMERA_ROAD":
        raise ValueError("unsupported road observation source")
    if (isinstance(stamp, bool) or not isinstance(stamp, (int, float))
            or not math.isfinite(float(stamp))):
        raise ValueError("road observation stamp must be finite")
    if not isinstance(map_id, str) or not map_id.strip():
        raise ValueError("road observation map_id is required")
    if not isinstance(scene_revision, str) or not scene_revision.strip():
        raise ValueError("road observation scene_revision is required")
    if not isinstance(observation, RoadObservation):
        raise ValueError("road observation is required")
    lane = observation.lane
    signal = observation.signal
    return {
        "source": source,
        "stamp": float(stamp),
        "map_id": map_id,
        "scene_revision": scene_revision,
        "lane": {
            "visible": lane is not None,
            "error": None if lane is None else float(lane.error),
            "confidence": 0.0 if lane is None else float(lane.confidence),
        },
        "stop_line": _marking_payload(observation.stop_line),
        "crosswalk": _marking_payload(observation.crosswalk),
        "signal": {
            "visible": signal is not None,
            "colour": None if signal is None else signal.colour,
            "confidence": 0.0 if signal is None else float(signal.confidence),
            "conflict": bool(observation.signal_conflict),
        },
    }
