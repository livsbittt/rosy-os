"""Match robots from YAML. No HTTP here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from rosy_games.field import Field


@dataclass(frozen=True)
class RobotEndpoint:
    robot_id: str
    url: str
    token: str = ""
    aruco_id: int = 0
    attacks: str = "positive_x"


@dataclass(frozen=True)
class MatchConfig:
    field: Field
    robots: tuple[RobotEndpoint, ...]
    limits_linear: float = 0.08
    limits_angular: float = 0.40


def load_match(path: Path) -> MatchConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pitch = raw.get("field") or {}
    robots = tuple(
        RobotEndpoint(
            robot_id=str(item["id"]),
            url=str(item.get("url") or ""),
            token=str(item.get("token") or ""),
            aruco_id=int(item.get("aruco_id") or 0),
            attacks=str(item.get("attacks") or "positive_x"),
        )
        for item in (raw.get("robots") or [])
    )
    if len(robots) < 2:
        raise ValueError("match config needs two robots")
    field = Field(
        length_m=float(pitch.get("width_m") or pitch.get("length_m") or 1.8),
        width_m=float(pitch.get("height_m") or 1.2),
        goal_width_m=float(pitch.get("goal_width_m") or 0.35),
        avoid_m=float(pitch.get("min_spacing_m") or 0.35),
        home_id=robots[0].robot_id,
        away_id=robots[1].robot_id,
    )
    limits = raw.get("limits") or {}
    return MatchConfig(
        field=field,
        robots=robots,
        limits_linear=float(limits.get("linear") or 0.08),
        limits_angular=float(limits.get("angular") or 0.40),
    )


def as_mapping(config: MatchConfig) -> Mapping[str, Any]:
    return {
        "robots": [item.robot_id for item in config.robots],
        "urls": [item.url for item in config.robots],
    }
