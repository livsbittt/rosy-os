"""rosy_core.capability — CAP-001~003 (P1-15, D-11, HWA-003). ROS 무의존."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, ValidationError

from rosy_core.profile import RobotProfile


class CapabilityError(Exception):
    def __init__(self, feature: str) -> None:
        super().__init__(f"capability not supported: {feature}")
        self.feature = feature


class CapabilityContractError(Exception):
    """Advertised capability is not a valid CAP-001 document or does not match profile+mode."""


class NavigationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_navigation: bool
    return_home: bool
    max_linear_velocity: float
    max_angular_velocity: float


class SwarmCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    follow: bool
    lead: bool


class DockingCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported: bool


class CapabilityDescriptor(BaseModel):
    """Machine schema for CAP-001. Unknown keys are a contract error."""

    model_config = ConfigDict(extra="forbid")

    capability_version: int
    navigation: NavigationCapability
    teleop: bool
    slam: bool
    swarm: SwarmCapability
    docking: DockingCapability
    sensors: list[str]
    events: list[str]
    api_versions: list[str]
    protocol_version: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


_CORE_EVENTS = (
    "safety.*",
    "mode.*",
    "waypoint.*",
    "system.*",
    "command.*",
)
_SENSOR_ORDER = ("lidar", "encoder", "imu", "battery")

# Served subset for each runtime mode. Profile sensors are the upper bound.
_MODE_POLICY: dict[str, dict[str, Any]] = {
    "core": {
        "goal_navigation": False,
        "return_home": False,
        "teleop": False,
        "slam": False,
        "follow": False,
        "lead": False,
        "sensors": frozenset(),
        "events": _CORE_EVENTS,
    },
    "motor": {
        "goal_navigation": False,
        "return_home": False,
        "teleop": True,
        "slam": False,
        "follow": False,
        "lead": False,
        "sensors": frozenset({"encoder"}),
        "events": _CORE_EVENTS,
    },
    "hardware": {
        "goal_navigation": True,
        "return_home": True,
        "teleop": True,
        "slam": False,
        "follow": False,
        "lead": False,
        "sensors": frozenset({"lidar", "encoder"}),
        "events": _CORE_EVENTS,
    },
}


def _walk(data: Any, dotted: str) -> Any:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def parse_capability(data: dict[str, Any]) -> CapabilityDescriptor:
    try:
        return CapabilityDescriptor.model_validate(data)
    except ValidationError as exc:
        raise CapabilityContractError(str(exc)) from exc


def derive_capability(profile: RobotProfile, mode: str) -> CapabilityDescriptor:
    try:
        policy = _MODE_POLICY[mode]
    except KeyError as exc:
        raise CapabilityContractError(
            f"unknown runtime mode {mode!r}; expected core, motor, or hardware"
        ) from exc

    present = set(profile.sensor_names)
    allowed: Iterable[str] = policy["sensors"]
    sensors = [name for name in _SENSOR_ORDER if name in present and name in allowed]
    linear = float(profile.max_linear_velocity if profile.max_linear_velocity is not None else 0.20)
    angular = float(
        profile.max_angular_velocity if profile.max_angular_velocity is not None else 0.80
    )
    return CapabilityDescriptor(
        capability_version=1,
        navigation=NavigationCapability(
            goal_navigation=policy["goal_navigation"],
            return_home=policy["return_home"],
            max_linear_velocity=linear,
            max_angular_velocity=angular,
        ),
        teleop=policy["teleop"],
        slam=policy["slam"],
        swarm=SwarmCapability(follow=policy["follow"], lead=policy["lead"]),
        docking=DockingCapability(supported=profile.docking_supported),
        sensors=sensors,
        events=list(policy["events"]),
        api_versions=["v1"],
        protocol_version="1.0",
    )


def bind_capability(
    profile: RobotProfile, mode: str, advertised: dict[str, Any]
) -> CapabilityDescriptor:
    """HWA-003: a capabilities file may exist only if it equals profile ∩ mode."""
    derived = derive_capability(profile, mode)
    parsed = parse_capability(advertised)
    if parsed.model_dump() != derived.model_dump():
        raise CapabilityContractError(
            "advertised capability does not match profile and runtime mode"
        )
    return derived


class Capability:
    """capabilities.yaml 로드 결과 (HWA-003: Profile이 원천)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = parse_capability(data).to_dict() if _looks_like_descriptor(data) else dict(data)

    @property
    def capability_version(self) -> int:
        return int(self._data.get("capability_version", 1))

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def supports(self, dotted: str) -> bool:
        value = _walk(self._data, dotted)
        return bool(value) if isinstance(value, bool) else value is not None

    def require(self, dotted: str) -> None:
        """CAP-003: 미지원 기능 요청 → CapabilityError (API 501 매핑)."""
        if not self.supports(dotted):
            raise CapabilityError(dotted)


def _looks_like_descriptor(data: dict[str, Any]) -> bool:
    return "navigation" in data and "swarm" in data and "protocol_version" in data
