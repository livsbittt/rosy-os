"""월드별 시뮬 숫자의 유일한 출처. ROS 무의존."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

CATALOG = Path(__file__).resolve().parent.parent / "config" / "worlds.yaml"


class WorldProfile:
    def __init__(
        self,
        world_name: str,
        map: str = "",
        inflation_radius: float = 0.0,
        spawn_x: float = 0.0,
        spawn_y: float = 0.0,
        spawn_spacing: float = 1.5,
    ) -> None:
        self.world_name = world_name
        self.map = map
        self.inflation_radius = inflation_radius
        self.spawn_x = spawn_x
        self.spawn_y = spawn_y
        self.spawn_spacing = spawn_spacing

    def overlay(self, **updates) -> "WorldProfile":
        payload = {
            "world_name": self.world_name,
            "map": self.map,
            "inflation_radius": self.inflation_radius,
            "spawn_x": self.spawn_x,
            "spawn_y": self.spawn_y,
            "spawn_spacing": self.spawn_spacing,
        }
        payload.update({k: v for k, v in updates.items() if v is not None})
        return WorldProfile(**payload)


def _key(world_name: str) -> str:
    name = Path(world_name).name
    return name if name.endswith(".world") else f"{name}.world"


def load_worlds(path: Path | None = None) -> dict[str, WorldProfile]:
    catalog = path or CATALOG
    raw = yaml.safe_load(catalog.read_text(encoding="utf-8")) or {}
    worlds = raw.get("worlds") or {}
    if not isinstance(worlds, dict) or not worlds:
        raise ValueError(f"{catalog}: worlds mapping is required")
    out: dict[str, WorldProfile] = {}
    for name, data in worlds.items():
        if not isinstance(data, dict):
            raise ValueError(f"{catalog}: {name} must be a mapping")
        out[_key(name)] = WorldProfile(
            world_name=_key(name),
            map=str(data.get("map") or ""),
            inflation_radius=float(data.get("inflation_radius") or 0.0),
            spawn_x=float(data.get("spawn_x") or 0.0),
            spawn_y=float(data.get("spawn_y") or 0.0),
            spawn_spacing=float(data.get("spawn_spacing") or 1.5),
        )
    return out


def spawn_xy(index: int, spawn_x: float, spawn_y: float, spacing: float) -> tuple[float, float]:
    """1-based robot index. x grows by spacing. Same numbers seed AMCL (D-115)."""
    if index < 1:
        raise ValueError(f"robot index must be >= 1, got {index}")
    return spawn_x + (index - 1) * spacing, spawn_y


def profile_for(world_name: str, path: Path | None = None) -> WorldProfile:
    worlds = load_worlds(path)
    key = _key(world_name)
    if key in worlds:
        return worlds[key]
    return WorldProfile(world_name=key)


def resolve_world(
    world_name: str,
    *,
    inflation_radius: Optional[float] = None,
    spawn_x: Optional[float] = None,
    spawn_y: Optional[float] = None,
    spawn_spacing: Optional[float] = None,
    map_yaml: Optional[str] = None,
    path: Path | None = None,
) -> WorldProfile:
    base = profile_for(world_name, path)
    updates = {}
    if inflation_radius is not None:
        updates["inflation_radius"] = inflation_radius
    if spawn_x is not None:
        updates["spawn_x"] = spawn_x
    if spawn_y is not None:
        updates["spawn_y"] = spawn_y
    if spawn_spacing is not None:
        updates["spawn_spacing"] = spawn_spacing
    if map_yaml:
        updates["map"] = map_yaml
    return base.overlay(**updates) if updates else base
