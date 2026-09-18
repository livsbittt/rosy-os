"""Ceiling camera. The only rosy_games module that may import cv2."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from rosy_games.field.homography import field_corners, fit
from rosy_games.game import Observation
from rosy_games.host.project import observation_from_pixels
from rosy_games.host.robots import MatchSetup

Point = tuple[float, float]


class OverheadCamera:
    def __init__(self, setup: MatchSetup, *, capture: Any = None) -> None:
        self.setup = setup
        self._owns = capture is None
        self._cap = capture
        if capture is None:
            self._cap = cv2.VideoCapture(setup.camera.index)
            if not self._cap.isOpened():
                raise RuntimeError(f"cannot open camera {setup.camera.index}")

    def observe(self) -> Observation:
        ok, frame = self._cap.read()
        if not ok:
            return self._lost()
        return self.observe_frame(frame)

    def observe_frame(self, bgr: np.ndarray) -> Observation:
        markers = detect_markers(bgr)
        homography = _homography(markers, self.setup)
        ball = detect_ball(bgr, self.setup.camera.hsv_low, self.setup.camera.hsv_high)
        robots = _robot_pixels(markers, self.setup)
        return observation_from_pixels(
            field=self.setup.field,
            homography=homography,
            ball_uv=ball,
            robots=robots,
            roster=(self.setup.field.home_id, self.setup.field.away_id),
        )

    def close(self) -> None:
        if self._owns and self._cap is not None:
            self._cap.release()
            self._cap = None

    def _lost(self) -> Observation:
        return observation_from_pixels(
            field=self.setup.field,
            homography=None,
            ball_uv=None,
            robots={},
            roster=(self.setup.field.home_id, self.setup.field.away_id),
        )


def detect_markers(bgr: np.ndarray) -> dict[int, np.ndarray]:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    corners, ids, _ = _detect(bgr, dictionary)
    if ids is None:
        return {}
    return {int(i): c[0] for i, c in zip(ids.flatten(), corners)}


def detect_ball(
    bgr: np.ndarray,
    hsv_low: tuple[int, int, int],
    hsv_high: tuple[int, int, int],
    *,
    min_area: float = 20.0,
) -> Point | None:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_low), np.array(hsv_high))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    blob = max(contours, key=cv2.contourArea)
    if cv2.contourArea(blob) < min_area:
        return None
    moments = cv2.moments(blob)
    if moments["m00"] == 0:
        return None
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def _detect(bgr: np.ndarray, dictionary: Any):
    try:
        detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
        return detector.detectMarkers(bgr)
    except AttributeError:
        return cv2.aruco.detectMarkers(bgr, dictionary)


def _homography(markers: dict[int, np.ndarray], setup: MatchSetup):
    pixels = []
    for marker_id in setup.camera.corner_ids:
        quad = markers.get(marker_id)
        if quad is None:
            return None
        pixels.append(_center(quad))
    return fit(tuple(pixels), field_corners(setup.field))


def _robot_pixels(markers: dict[int, np.ndarray], setup: MatchSetup) -> dict[str, tuple[Point, Point]]:
    out: dict[str, tuple[Point, Point]] = {}
    for robot in setup.robots:
        quad = markers.get(robot.aruco_id)
        if quad is None:
            continue
        center = _center(quad)
        tip = (float(quad[1][0]), float(quad[1][1]))
        out[robot.id] = (center, tip)
    return out


def _center(quad: np.ndarray) -> Point:
    return float(quad[:, 0].mean()), float(quad[:, 1].mean())
