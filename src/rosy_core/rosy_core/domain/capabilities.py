"""rosy_core.domain.capabilities — CAP-001 flags → concept descriptor ids. ROS 무의존."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# Design §7. False flags are omitted. manipulate.pick / scan_rfid / infer / train stay off.
_CAP001_TO_CONCEPT: tuple[tuple[str, str], ...] = (
    ("teleop", "mobility.move"),
    ("navigation.goal_navigation", "mobility.navigate"),
    ("swarm.follow", "mobility.follow"),
    ("swarm.lead", "mobility.lead"),
    ("docking.supported", "mobility.dock"),
    ("slam", "perception.localize"),
)


@dataclass(frozen=True)
class CapabilityDescriptor:
    id: str


def _flag_is_true(data: Any, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node is True


def descriptors_from_cap001(data: Mapping[str, Any]) -> tuple[CapabilityDescriptor, ...]:
    return tuple(
        CapabilityDescriptor(id=concept_id)
        for flag, concept_id in _CAP001_TO_CONCEPT
        if _flag_is_true(data, flag)
    )
