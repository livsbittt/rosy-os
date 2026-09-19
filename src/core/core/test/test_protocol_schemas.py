"""protocol 스키마 단위 테스트 (P1-19) — ROSY-API-REF-001 §7 대응."""

import pytest

from core_common.protocol.schemas import (
    AckPayload,
    AckStatus,
    Envelope,
    EnvelopeType,
    EventMessage,
    PoseSample,
    RobotMode,
    Severity,
    StateSnapshot,
    SwarmFollowParams,
    SwarmRole,
    SwarmStatus,
)


def test_robot_mode_has_no_soccer():
    """D-90: 축구는 게임 호스트다. CORE 모드가 아니다."""
    assert "SOCCER" not in RobotMode.__members__
    assert set(RobotMode) == {
        RobotMode.IDLE,
        RobotMode.MANUAL,
        RobotMode.NAVIGATION,
        RobotMode.DOCKING,
        RobotMode.EMERGENCY,
    }


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
    assert snap.evidence == {}


def test_state_snapshot_evidence_is_additive():
    """v1.8: evidence 없는 구 페이로드도 읽고, 모르는 채널 키는 유지한다(API-002)."""
    dumped = StateSnapshot(robot_id="rosy_01").model_dump()
    dumped.pop("evidence", None)
    restored = StateSnapshot.model_validate(dumped)
    assert restored.evidence == {}

    from core_common.protocol.evidence import EvidenceState, ValueEvidence

    snap = StateSnapshot(
        robot_id="rosy_01",
        evidence={
            "pose": ValueEvidence(evidence=EvidenceState.FRESH, stale_after_s=2.0),
            "custom_channel": ValueEvidence(evidence=EvidenceState.UNAVAILABLE),
        },
    )
    roundtrip = StateSnapshot.model_validate(snap.model_dump())
    assert roundtrip.evidence["pose"].evidence is EvidenceState.FRESH
    assert "custom_channel" in roundtrip.evidence


def test_swarm_status_additive_default():
    """v1.1 additive: swarm 필드 기본값 — 기존 소비자 영향 없음 (CAP-002)."""
    snap = StateSnapshot(robot_id="rosy_01")
    assert snap.swarm.role == SwarmRole.NONE
    assert snap.swarm.active is False
    snap2 = StateSnapshot.model_validate(snap.model_dump())  # 직렬화 왕복
    assert snap2.swarm.role == SwarmRole.NONE


def test_swarm_follow_params_defaults():
    p = SwarmFollowParams(target_robot_id="rosy_02")
    assert p.distance == 0.5 and p.lateral == 0.0
    assert p.max_speed == 0.15 and p.stream_timeout_ms == 1000
    assert p.source.value == "fleet"  # v1.2 additive 기본값 — 기존 소비자 호환 (D-21)


def test_pose_stream_envelope():
    sample = PoseSample(robot_id="rosy_01", pose={"x": 1.0, "y": 0.0, "yaw": 0.1}, seq=1)
    env = Envelope(type=EnvelopeType.POSE, payload=sample.model_dump())
    assert Envelope.model_validate(env.model_dump()).type == EnvelopeType.POSE
    parsed = PoseSample.model_validate(env.payload)
    assert parsed.pose.x == 1.0 and parsed.seq == 1
