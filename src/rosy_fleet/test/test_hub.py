"""SiteHub는 계약 envelope만 모은다. 바퀴 속도와 원본 영상은 거절한다 (D-59)."""

from rosy_core.protocol.schemas import (
    Envelope,
    EnvelopeType,
    EventMessage,
    HeartbeatPayload,
    HelloPayload,
    StateSnapshot,
)
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.hub.hub import SiteHub


def _ep(robot_id: str = "rosy_01") -> RobotEndpoint:
    return RobotEndpoint(robot_id, "http://127.0.0.1:8080", "pair-01")


def _hello(robot_id="rosy_01", token="pair-01") -> Envelope:
    payload = HelloPayload(robot_id=robot_id, pairing_token=token).model_dump()
    return Envelope(type=EnvelopeType.HELLO, payload=payload)


def test_hello_with_known_token_is_welcomed_and_listed_online():
    hub = SiteHub([_ep()])
    reply = hub.handle(_hello())
    assert reply.type is EnvelopeType.WELCOME
    assert reply.payload["robot_id"] == "rosy_01"
    assert hub.registry.online_ids() == ["rosy_01"]


def test_hello_with_wrong_token_is_pairing_invalid_and_stays_offline():
    hub = SiteHub([_ep()])
    reply = hub.handle(_hello(token="nope"))
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "PAIRING_INVALID"
    assert hub.registry.online_ids() == []
