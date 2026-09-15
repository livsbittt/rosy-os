"""rosy_core.profile — HWA-001 Robot Profile 로더 (P1-15)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml


class RobotProfile:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data.get("profile", data)

    @classmethod
    def load(cls, path: Path) -> "RobotProfile":
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    @property
    def model(self) -> str:
        return str(self._data.get("model", "unknown"))

    @property
    def max_linear_velocity(self) -> Optional[float]:
        v = self._data.get("max_linear_velocity")
        return float(v) if v is not None else None

    @property
    def max_angular_velocity(self) -> Optional[float]:
        v = self._data.get("max_angular_velocity")
        return float(v) if v is not None else None

    @property
    def sensor_names(self) -> tuple[str, ...]:
        raw = self._data.get("sensors") or []
        names: list[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                names.extend(str(key) for key in item.keys())
        return tuple(names)

    @property
    def docking_supported(self) -> bool:
        docking = self._data.get("docking")
        if isinstance(docking, dict):
            return bool(docking.get("supported"))
        return bool(docking)
