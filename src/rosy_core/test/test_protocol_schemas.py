"""protocol 스키마 단위 테스트 (P1-19) — ROSY-API-REF-001 §7 대응."""

import pytest

from rosy_core.protocol.schemas import (
    AckPayload,
    AckStatus,
    Envelope,
    EnvelopeType,
    EventMessage,
    Severity,
    StateSnapshot,
)


def test_envelope_defaults():
    env = Envelope(type=EnvelopeType.HEARTBEAT, payload={})
    assert env.protocol_version == "1.0"
    assert env.msg_id
    assert env.correlation_id is None


def test_envelope_roundtrip():
    env = Envelope(type=EnvelopeType.ACK, correlation_id="c-1", payload=AckPayload(status=AckStatus.ACCEPTED).model_dump())
    assert Envelope.model_validate(env.model_dump()) == env


def test_event_model_seq_monotone_field():
    e1 = EventMessage(seq=1, robot_id="rosy_01", type="nav.completed")
    e2 = EventMessage(seq=2, robot_id="rosy_01", type="safety.estop", severity=Severity.CRITICAL)
    assert e2.seq > e1.seq
    assert e1.event_id != e2.event_id


def test_state_snapshot_defaults():
    snap = StateSnapshot(robot_id="rosy_01")
    assert snap.mode.value == "IDLE"
    assert snap.navigation.value == "IDLE"
