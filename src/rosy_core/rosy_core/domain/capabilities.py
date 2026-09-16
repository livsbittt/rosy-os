"""rosy_core.domain.capabilities — CAP-001 flags → concept descriptor ids. ROS 무의존."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from rosy_core.domain.model import DeviceState

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


@dataclass(frozen=True)
class CapabilityDescriptor:
    id: str
    available: bool = True


def _flag_is_true(data: Any, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node is True


def descriptors_from_cap001(
    data: Mapping[str, Any],
    *,
    device_state: Optional[DeviceState] = None,
) -> tuple[CapabilityDescriptor, ...]:
    available = (
        True
        if device_state is None
        else device_state not in _UNAVAILABLE_STATES
    )
    return tuple(
        CapabilityDescriptor(id=concept_id, available=available)
        for flag, concept_id in _CAP001_TO_CONCEPT
        if _flag_is_true(data, flag)
    )
