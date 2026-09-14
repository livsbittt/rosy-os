"""관제 쪽 모음/흩뿌림. 최종 cmd_vel과 Image를 다루지 않는다 (D-59)."""

from __future__ import annotations

from typing import Optional, Sequence

from rosy_core.protocol.schemas import (
    Envelope,
    EnvelopeType,
    HelloPayload,
    WelcomePayload,
)
from rosy_fleet.hub.registry import RobotRegistry
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.swarm.transport import RobotClient


def _error(code: str, message: str) -> Envelope:
    return Envelope(type=EnvelopeType.ERROR, payload={"code": code, "message": message})


class SiteHub:
    def __init__(
        self,
        endpoints: Sequence[RobotEndpoint],
        clients: Optional[dict[str, RobotClient]] = None,
        fleet_name: str = "rosy-site",
    ) -> None:
        self._tokens = {e.robot_id: e.token for e in endpoints}
        self._clients = clients or {}
        self._paired: set[str] = set()
        self.registry = RobotRegistry()
        self._fleet_name = fleet_name

    def handle(self, envelope: Envelope) -> Envelope:
        if envelope.type is EnvelopeType.HELLO:
            return self._hello(envelope)
        return _error("SESSION_NOT_PAIRED", "hello first")

    def _hello(self, envelope: Envelope) -> Envelope:
        try:
            hello = HelloPayload.model_validate(envelope.payload)
        except Exception:
            return _error("PAIRING_INVALID", "bad hello")
        expected = self._tokens.get(hello.robot_id)
        if expected is None or expected != hello.pairing_token:
            return _error("PAIRING_INVALID", "unknown robot or token")
        row = self.registry.record(hello.robot_id)
        row.online = True
        self._paired.add(hello.robot_id)
        welcome = WelcomePayload(
            robot_id=hello.robot_id,
            fleet_name=self._fleet_name,
        )
        return Envelope(type=EnvelopeType.WELCOME, payload=welcome.model_dump())
