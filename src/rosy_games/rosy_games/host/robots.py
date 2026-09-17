"""CORE endpoints as match.yaml robot rows. No HTTP here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotEndpoint:
    id: str
    url: str
    token: str
    aruco_id: int
    attacks: str
