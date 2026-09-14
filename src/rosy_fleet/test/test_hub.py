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


def test_heartbeat_before_hello_is_rejected():
    hub = SiteHub([_ep()])
    snap = StateSnapshot(robot_id="rosy_01")
    env = Envelope(
        type=EnvelopeType.HEARTBEAT,
        payload=HeartbeatPayload(state_snapshot=snap).model_dump(mode="json"),
    )
    reply = hub.handle(env)
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "SESSION_NOT_PAIRED"


def test_heartbeat_updates_registry_snapshot():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    snap = StateSnapshot(robot_id="rosy_01", seq=4)
    env = Envelope(
        type=EnvelopeType.HEARTBEAT,
        payload=HeartbeatPayload(state_snapshot=snap).model_dump(mode="json"),
    )
    reply = hub.handle(env)
    assert reply.type is not EnvelopeType.ERROR
    stored = hub.registry.record("rosy_01").snapshot
    assert stored is not None
    assert stored.seq == 4


def test_events_are_kept_in_seq_order_and_gap_fill_reads_since_seq():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    for seq in (1, 2, 3):
        event = EventMessage(seq=seq, robot_id="rosy_01", type="nav.completed")
        hub.handle(Envelope(type=EnvelopeType.EVENT, payload=event.model_dump(mode="json")))
    filled = hub.registry.events_since("rosy_01", since_seq=1)
    assert [e.seq for e in filled] == [2, 3]


def test_event_robot_id_mismatch_after_hello_is_pairing_invalid():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    event = EventMessage(seq=1, robot_id="rosy_99", type="nav.completed")
    reply = hub.handle(Envelope(type=EnvelopeType.EVENT, payload=event.model_dump(mode="json")))
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "PAIRING_INVALID"
