"""core_common.domain.capabilities — CAP-001 flags → concept descriptor ids. ROS 무의존."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from core_common.domain.model import DeviceState

# Design §7. False flags are omitted. manipulate.pick / scan_rfid / infer / train stay off.
_CAP001_TO_CONCEPT: tuple[tuple[str, str], ...] = (
    ("teleop", "mobility.move"),
    ("navigation.goal_navigation", "mobility.navigate"),
    ("swarm.follow", "mobility.follow"),
    ("swarm.lead", "mobility.lead"),
    ("docking.supported", "mobility.dock"),
    ("slam", "perception.localize"),
)

# Concept 07 §5: availability depends on device state. YAML advertisement
# (CAP-001) stays true; inventory descriptors drop available during these.
_UNAVAILABLE_STATES = {
    DeviceState.BOOTING,
    DeviceState.FAULT,
    DeviceState.SAFE_STOP,
    DeviceState.OFFLINE,
    DeviceState.UPDATING,
}


class PresentationState(str, enum.Enum):
    """concept 16 §8. `not_provided` is the S7 rename of `absent` (token clash)."""

    AVAILABLE = "available"
    CONSTRAINED = "constrained"
    DEGRADED_FALLBACK = "degraded_fallback"
    BLOCKED = "blocked"
    NOT_PROVIDED = "not_provided"


@dataclass(frozen=True)
class CapabilityDescriptor:
    id: str
    available: bool = True
    state: str = PresentationState.AVAILABLE.value
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.state == PresentationState.BLOCKED.value and not self.reason:
            raise ValueError("blocked capability requires a reason")


def _flag_is_true(data: Any, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node is True


def _presentation(device_state: Optional[DeviceState]) -> tuple[bool, str, Optional[str]]:
    if device_state is None:
        return True, PresentationState.AVAILABLE.value, None
    if device_state in _UNAVAILABLE_STATES:
        return (
            False,
            PresentationState.BLOCKED.value,
            f"device_state:{device_state.value}",
        )
    if device_state is DeviceState.DEGRADED:
        return (
            True,
            PresentationState.DEGRADED_FALLBACK.value,
            f"device_state:{device_state.value}",
        )
    return True, PresentationState.AVAILABLE.value, None


def descriptors_from_cap001(
    data: Mapping[str, Any],
    *,
    device_state: Optional[DeviceState] = None,
) -> tuple[CapabilityDescriptor, ...]:
    available, state, reason = _presentation(device_state)
    return tuple(
        CapabilityDescriptor(
            id=concept_id, available=available, state=state, reason=reason
        )
        for flag, concept_id in _CAP001_TO_CONCEPT
        if _flag_is_true(data, flag)
    )
