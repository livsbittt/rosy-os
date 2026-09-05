"""SWM-003 리더 pose 스트림과 팔로워 참조 스트림 입구 (API Ref §7.8).

두 소켓이 같은 envelope 을 쓰는 것이 이 이야기의 요점이다. 리더의
`/ws/swarm/pose` 출력을 팔로워의 `/ws/swarm/reference` 에 그대로 넣을 수
있어야, 추종 로직이 소스를 묻지 않는다는 SWM-007 이 말이 아니라 성질이 된다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from rosy_core.api.app import create_app
from rosy_core.profile import RobotProfile
from rosy_core.protocol.schemas import EnvelopeType
from rosy_core.services import CoreServices

CONFIG_DIR = Path(__file__).parent.parent / "config"

ADMIN_TOKEN = "rosy-dev-admin"
OPERATOR_TOKEN = "rosy-dev-operator"
VIEWER_TOKEN = "rosy-dev-viewer"


@pytest.fixture
def client(tmp_path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    config = yaml.safe_load((CONFIG_DIR / "rosy_default.yaml").read_text(encoding="utf-8"))
    profile = RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml")
    caps = yaml.safe_load((CONFIG_DIR / "capabilities.yaml").read_text(encoding="utf-8"))
    caps["swarm"] = {"follow": True, "lead": True}
    services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
    return TestClient(create_app(config, services)), services


class RecordingNav:
    def __init__(self) -> None:
        self.goals = []
        self.cancels = []

    def moving_goal(self, spec, source="swarm"):
        self.goals.append(spec)

    def cancel(self, source="api"):
        self.cancels.append(source)


def follow(tc, target="rosy_02"):
    response = tc.post(
        "/api/v1/swarm/follow",
        json={"target_robot_id": target, "distance": 0.5, "lateral": 0.0},
        headers={"Authorization": f"Bearer {OPERATOR_TOKEN}"},
    )
    assert response.status_code == 200


def pose_frame(robot_id="rosy_02", x=1.0, y=2.0, yaw=0.0, seq=1):
    return {
        "protocol_version": "1.0",
        "msg_id": "test",
        "type": "pose",
        "ts": "2026-09-06T00:00:00Z",
        "payload": {"robot_id": robot_id, "pose": {"x": x, "y": y, "yaw": yaw}, "seq": seq},
    }


# --- SWM-003 리더 pose 스트림 ---------------------------------------------------


def test_the_leader_stream_sends_the_contract_envelope(client):
    tc, svc = client
    svc.state.set_pose(1.5, -0.25, 0.75)

    with tc.websocket_connect(f"/ws/swarm/pose?token={VIEWER_TOKEN}") as socket:
        frame = socket.receive_json()

    assert frame["type"] == EnvelopeType.POSE.value
    assert frame["protocol_version"] == "1.0"
    assert frame["msg_id"] and frame["ts"]
    assert frame["payload"]["robot_id"] == svc.identity.robot_id
    assert frame["payload"]["pose"] == {"x": 1.5, "y": -0.25, "yaw": 0.75}
    assert frame["payload"]["seq"] == 1


def test_the_leader_stream_advances_its_sequence(client):
    tc, _svc = client

    with tc.websocket_connect(f"/ws/swarm/pose?token={VIEWER_TOKEN}") as socket:
        first = socket.receive_json()
        second = socket.receive_json()

    assert second["payload"]["seq"] == first["payload"]["seq"] + 1


def test_the_leader_rate_cannot_be_configured_below_the_requirement(tmp_path):
    """SWM-003 의 10 Hz 는 하한이다. 설정으로 내려가면 대형이 흔들린다."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    config = yaml.safe_load((CONFIG_DIR / "rosy_default.yaml").read_text(encoding="utf-8"))
    config["swarm"] = {"pose_rate_hz": 1.0}
    profile = RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml")
    caps = yaml.safe_load((CONFIG_DIR / "capabilities.yaml").read_text(encoding="utf-8"))
    services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
    tc = TestClient(create_app(config, services))

    import time

    frames = 20
    with tc.websocket_connect(f"/ws/swarm/pose?token={VIEWER_TOKEN}") as socket:
        socket.receive_json()
        started = time.monotonic()
        for _ in range(frames):
            socket.receive_json()
        elapsed = time.monotonic() - started

    achieved = frames / elapsed
    # 서버는 마감시각을 따라가므로 예약 주기는 정확히 1/rate 다. 남는 오차는
    # TestClient 가 같은 프로세스에서 프레임을 받아가는 비용이다. 보낸 뒤에
    # period 만큼 자던 예전 구현은 여기서 ~9.2 Hz 로 측정됐다.
    assert achieved >= 9.5, f"SWM-003 asks for >=10 Hz; measured {achieved:.2f} Hz"


# --- 참조 스트림 입구 -----------------------------------------------------------


def test_a_reference_frame_reaches_the_swarm_manager(client):
    tc, svc = client
    svc.swarm.nav = RecordingNav()
    follow(tc)

    with tc.websocket_connect(f"/ws/swarm/reference?token={OPERATOR_TOKEN}") as socket:
        socket.send_text(json.dumps(pose_frame(x=1.0, y=0.0, yaw=0.0)))
        socket.send_text(json.dumps({"type": "ping"}))  # 응답을 기다릴 순서 보장용

    assert len(svc.swarm.nav.goals) == 1
    assert svc.swarm.nav.goals[0].x == pytest.approx(0.5)  # 1.0 - distance 0.5


def test_a_leader_frame_can_be_fed_straight_into_a_follower(client):
    """리더 소켓의 출력이 팔로워 소켓의 입력이다 (SWM-007)."""
    tc, svc = client
    svc.swarm.nav = RecordingNav()
    svc.state.set_pose(4.0, 0.0, 0.0)

    with tc.websocket_connect(f"/ws/swarm/pose?token={VIEWER_TOKEN}") as leader:
        emitted = leader.receive_json()

    follow(tc, target=emitted["payload"]["robot_id"])
    with tc.websocket_connect(f"/ws/swarm/reference?token={OPERATOR_TOKEN}") as socket:
        socket.send_text(json.dumps(emitted))
        socket.send_text(json.dumps({"type": "ping"}))

    assert len(svc.swarm.nav.goals) == 1
    assert svc.swarm.nav.goals[0].x == pytest.approx(3.5)


@pytest.mark.parametrize("frame", [
    {"type": "heartbeat", "payload": {}},
    {"type": "pose"},
    {"type": "pose", "payload": {"robot_id": "rosy_02"}},
    {"type": "pose", "payload": {"robot_id": "", "pose": {"x": 1, "y": 1, "yaw": 0}}},
    {"type": "pose", "payload": {"robot_id": "rosy_02", "pose": {"x": "nope", "y": 1, "yaw": 0}}},
    {"type": "pose", "payload": {"robot_id": "rosy_02", "pose": {"x": 1}}},
    [1, 2, 3],
])
def test_a_malformed_frame_is_dropped_without_closing_the_socket(client, frame):
    """한 프레임이 망가졌다고 닫으면 표본 하나가 대형을 HOLD 로 떨어뜨린다."""
    tc, svc = client
    svc.swarm.nav = RecordingNav()
    follow(tc)

    with tc.websocket_connect(f"/ws/swarm/reference?token={OPERATOR_TOKEN}") as socket:
        socket.send_text(json.dumps(frame))
        socket.send_text("this is not json at all")
        socket.send_text(json.dumps(pose_frame(x=2.0)))
        socket.send_text(json.dumps({"type": "ping"}))

    assert len(svc.swarm.nav.goals) == 1, "the socket survived and the good frame got through"
    assert svc.swarm.nav.goals[0].x == pytest.approx(1.5)


def test_a_reference_for_another_robot_changes_nothing(client):
    tc, svc = client
    svc.swarm.nav = RecordingNav()
    follow(tc, target="rosy_02")

    with tc.websocket_connect(f"/ws/swarm/reference?token={OPERATOR_TOKEN}") as socket:
        socket.send_text(json.dumps(pose_frame(robot_id="rosy_77")))
        socket.send_text(json.dumps({"type": "ping"}))

    assert svc.swarm.nav.goals == []


# --- 인증 -----------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/ws/swarm/pose", "/ws/swarm/reference"])
def test_a_bad_token_is_closed_with_4401_like_ws_state(client, path):
    tc, _svc = client
    from starlette.websockets import WebSocketDisconnect

    for query in ("", "?token=", "?token=nope"):
        with pytest.raises(WebSocketDisconnect) as raised:
            with tc.websocket_connect(f"{path}{query}") as socket:
                socket.receive_json()
        assert raised.value.code == 4401


def test_the_reference_socket_requires_an_operator(client):
    """읽기는 viewer 로 되지만, 로봇을 움직이는 스트림을 밀어 넣는 것은 아니다.

    4401 은 토큰이 없거나 틀린 것이고, 인증은 됐는데 허용되지 않는 것은 4403 이다.
    """
    tc, _svc = client
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as raised:
        with tc.websocket_connect(f"/ws/swarm/reference?token={VIEWER_TOKEN}") as socket:
            socket.send_text(json.dumps(pose_frame()))
            socket.receive_json()
    assert raised.value.code == 4403

    with tc.websocket_connect(f"/ws/swarm/reference?token={ADMIN_TOKEN}") as socket:
        socket.send_text(json.dumps(pose_frame()))


def test_the_leader_socket_is_closed_when_lead_is_not_declared(tmp_path):
    """CAP-003: 선언하지 않은 기능을 소켓으로 우회 제공하면 CAP-001 이 거짓말이 된다."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    config = yaml.safe_load((CONFIG_DIR / "rosy_default.yaml").read_text(encoding="utf-8"))
    profile = RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml")
    caps = yaml.safe_load((CONFIG_DIR / "capabilities.yaml").read_text(encoding="utf-8"))
    caps["swarm"] = {"follow": True, "lead": False}
    services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
    tc = TestClient(create_app(config, services))

    with pytest.raises(WebSocketDisconnect) as raised:
        with tc.websocket_connect(f"/ws/swarm/pose?token={VIEWER_TOKEN}") as socket:
            socket.receive_json()

    assert raised.value.code == 4403
