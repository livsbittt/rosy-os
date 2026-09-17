"""CORE endpoints as match.yaml robot rows. No HTTP here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from rosy_games.field import Field


@dataclass(frozen=True)
class RobotEndpoint:
    id: str
    url: str
    token: str
    aruco_id: int
    attacks: str


def load_match(path: Path) -> tuple[Field, list[RobotEndpoint]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    row = data.get("field") or {}
    robots = [
        RobotEndpoint(
            id=str(item["id"]),
            url=str(item["url"]).rstrip("/"),
            token=str(item.get("token") or ""),
            aruco_id=int(item["aruco_id"]),
            attacks=str(item["attacks"]),
        )
        for item in data.get("robots") or []
    ]
    if len(robots) != 2:
        raise ValueError(f"{path}: needs exactly two robots")
    field = Field(
        length_m=float(row["length_m"]),
        width_m=float(row["width_m"]),
        goal_width_m=float(row["goal_width_m"]),
        min_spacing_m=float(row["min_spacing_m"]),
        home_id=robots[0].id,
        away_id=robots[1].id,
    )
    return field, robots
