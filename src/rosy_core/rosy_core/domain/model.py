"""rosy_core.domain.model — concept Node/Device/Component/Asset snapshot. ROS 무의존."""

from __future__ import annotations

import enum
import platform
import socket
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from rosy_core.identity import SOFTWARE_VERSION

_SLICES_BY_MODE = {
    "core": ("core",),
    "motor": ("core", "motor"),
    "hardware": ("core", "motor", "io", "nav"),
}


class DeviceState(str, enum.Enum):
    BOOTING = "BOOTING"
    READY = "READY"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    SAFE_STOP = "SAFE_STOP"
    OFFLINE = "OFFLINE"
    UPDATING = "UPDATING"


@dataclass(frozen=True)
class RuntimeNode:
    runtime_mode: str
    slices: tuple[str, ...]
    hostname: str = ""
    architecture: str = ""
    os: str = ""
    software_version: str = SOFTWARE_VERSION


@dataclass(frozen=True)
class Device:
    device_id: str
    device_type: str
    model: str = ""


@dataclass(frozen=True)
class Component:
    name: str


@dataclass(frozen=True)
class Asset:
    asset_id: str
    type: str
    devices: tuple[str, ...]


def slices_from_config(config: dict[str, Any]) -> tuple[str, ...]:
    runtime = config.get("runtime") or {}
    raw = runtime.get("slices")
    if raw is None:
        raw = config.get("slices")
    if raw:
        return tuple(str(item) for item in raw)
    mode = str(runtime.get("mode") or "core")
    return _SLICES_BY_MODE.get(mode, ("core",))


def _mode_value(mode: Any) -> str:
    value = getattr(mode, "value", mode)
    return str(value)


def _device_state(mode: Any, health_error: bool, estop: bool) -> DeviceState:
    value = _mode_value(mode)
    if estop or value == "EMERGENCY":
        return DeviceState.SAFE_STOP
    if health_error:
        return DeviceState.FAULT
    if value in {"NAVIGATION", "DOCKING", "MANUAL"}:
        return DeviceState.BUSY
    return DeviceState.READY


def _components(sensors: Iterable[str]) -> tuple[Component, ...]:
    names: list[str] = []
    for name in ("drive", *sensors):
        text = str(name)
        if text and text not in names:
            names.append(text)
    return tuple(Component(name=name) for name in names)


def inventory_from_config(
    config: dict[str, Any],
    *,
    profile_model: str,
    sensors: Sequence[str],
    slices: Optional[Sequence[str]] = None,
    mode: Any,
    health_error: bool,
    estop: bool,
) -> dict[str, Any]:
    robot = config.get("robot") or {}
    robot_id = str(robot.get("id") or "rosy_01")
    runtime = config.get("runtime") or {}
    resolved_slices = (
        tuple(str(item) for item in slices)
        if slices is not None
        else slices_from_config(config)
    )
    return {
        "node": RuntimeNode(
            runtime_mode=str(runtime.get("mode") or "core"),
            slices=resolved_slices,
            hostname=socket.gethostname(),
            architecture=platform.machine(),
            os=platform.system(),
            software_version=SOFTWARE_VERSION,
        ),
        "device": Device(
            device_id=robot_id,
            device_type="mobile_base",
            model=profile_model,
        ),
        "components": _components(sensors),
        "asset": Asset(
            asset_id=robot_id,
            type="mobile_base",
            devices=(robot_id,),
        ),
        "device_state": _device_state(mode, health_error, estop),
    }
