"""Last OccupancyGrid / Path / Costmap snapshots for MAP-003. ROS-free."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Any, Optional

_COSTMAP_SCOPES = frozenset({"global", "local"})


@dataclass(frozen=True)
class GridFrame:
    """World-frame occupancy / cost grid. Origin yaw is stored but sampling is axis-aligned."""

    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    origin_yaw: float = 0.0
    data: tuple[int, ...] = ()

    @classmethod
    def from_dict(cls, grid: dict[str, Any]) -> "GridFrame":
        origin = grid.get("origin") or {}
        raw = grid.get("data") or ()
        return cls(
            width=int(grid["width"]),
            height=int(grid["height"]),
            resolution=float(grid["resolution"]),
            origin_x=float(origin.get("x", 0.0)),
            origin_y=float(origin.get("y", 0.0)),
            origin_yaw=float(origin.get("yaw", 0.0)),
            data=tuple(int(value) for value in raw),
        )

    def world_to_cell(self, x: float, y: float) -> Optional[tuple[int, int]]:
        if self.resolution <= 0 or self.width <= 0 or self.height <= 0:
            return None
        column = math.floor((float(x) - self.origin_x) / self.resolution)
        row = math.floor((float(y) - self.origin_y) / self.resolution)
        if 0 <= column < self.width and 0 <= row < self.height:
            return column, row
        return None

    def sample_world(self, x: float, y: float) -> Optional[int]:
        cell = self.world_to_cell(x, y)
        if cell is None or not self.data:
            return None
        column, row = cell
        index = row * self.width + column
        if index >= len(self.data):
            return None
        return self.data[index]

    def sample_other(self, other: "GridFrame", x: float, y: float) -> Optional[int]:
        return other.sample_world(x, y)


def valid_costmap_scope(scope: str) -> bool:
    return scope in _COSTMAP_SCOPES


class MapSnapshotStore:
    """Bridge writes, REST reads. Missing map/costmap is None, not an empty grid."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map: Optional[dict[str, Any]] = None
        self._path: list[dict[str, float]] = []
        self._costmaps: dict[str, dict[str, Any]] = {}

    def set_map(self, grid: dict[str, Any]) -> None:
        with self._lock:
            self._map = dict(grid)

    def get_map(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return None if self._map is None else dict(self._map)

    def set_path(self, poses: list[dict[str, float]]) -> None:
        with self._lock:
            self._path = list(poses)

    def get_path(self) -> list[dict[str, float]]:
        with self._lock:
            return list(self._path)

    def set_costmap(self, scope: str, grid: dict[str, Any]) -> None:
        if not valid_costmap_scope(scope):
            raise ValueError(f"costmap scope must be global or local, got {scope!r}")
        with self._lock:
            self._costmaps[scope] = dict(grid)

    def get_costmap(self, scope: str) -> Optional[dict[str, Any]]:
        if not valid_costmap_scope(scope):
            raise ValueError(f"costmap scope must be global or local, got {scope!r}")
        with self._lock:
            grid = self._costmaps.get(scope)
            return None if grid is None else dict(grid)
