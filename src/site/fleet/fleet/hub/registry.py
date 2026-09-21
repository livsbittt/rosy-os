"""로봇 기록. 전송·ROS 없음."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core_common.protocol.schemas import EventMessage, StateSnapshot


@dataclass
class RobotRecord:
    robot_id: str
    online: bool = False
    device_uid: str = ""
    device_name: str = ""
    model: str = ""
    hardware_serial: str = ""
    snapshot: Optional[StateSnapshot] = None
    last_event_seq: int = 0
    events: list[EventMessage] = field(default_factory=list)


class RobotRegistry:
    def __init__(self) -> None:
        self._robots: dict[str, RobotRecord] = {}

    def record(self, robot_id: str) -> RobotRecord:
        row = self._robots.get(robot_id)
        if row is None:
            row = RobotRecord(robot_id=robot_id)
            self._robots[robot_id] = row
        return row

    def online_ids(self) -> list[str]:
        return sorted(r.robot_id for r in self._robots.values() if r.online)

    def events_since(self, robot_id: str, since_seq: int) -> list[EventMessage]:
        row = self._robots.get(robot_id)
        if row is None:
            return []
        return [e for e in row.events if e.seq > since_seq]
