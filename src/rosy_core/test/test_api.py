"""API 통합 테스트 — 실제 서비스(ROS 무의존) + FastAPI TestClient (P1-9)."""

import importlib

import pytest

fastapi_test = importlib.import_module  # noqa: F841

from pathlib import Path

from rosy_core.api.app import create_app
from rosy_core.profile import RobotProfile
from rosy_core.services import CoreServices

import yaml


@pytest.fixture
def client(tmp_path):
    httpx = pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    config = yaml.safe_load((Path(__file__).parent.parent / "config" / "rosy_default.yaml").read_text())
    profile = RobotProfile.load(Path(__file__).parent.parent / "config" / "profile.pinky_pro.yaml")
    caps = yaml.safe_load((Path(__file__).parent.parent / "config" / "capabilities.yaml").read_text())
    services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
    app = create_app(config, services)
    return TestClient(app), services


ADMIN = {"Authorization": "Bearer rosy-dev-admin"}
OPERATOR = {"Authorization": "Bearer rosy-dev-operator"}
VIEWER = {"Authorization": "Bearer rosy-dev-viewer"}


def test_system_info_and_capabilities(client):
    tc, svc = client
    r = tc.get("/api/v1/system/info", headers=VIEWER)
    assert r.status_code == 200
    assert r.json()["robot_id"] == "rosy_01"
    assert r.json()["hardware_model"] == "Pinky Pro"
    r = tc.get("/api/v1/system/capabilities", headers=VIEWER)
    assert r.json()["swarm"] == {"follow": True, "lead": True}


def test_auth_roles(client):
    tc, _ = client
    assert tc.get("/api/v1/robot/state").status_code == 401            # UNAUTHORIZED
    assert tc.get("/api/v1/robot/state", headers=VIEWER).status_code == 200
    assert tc.post("/api/v1/teleop", json={}, headers=VIEWER).status_code == 403   # FORBIDDEN
    assert tc.post("/api/v1/teleop", json={}, headers=OPERATOR).status_code in (200, 409)
    assert tc.post("/api/v1/safety/release", headers=OPERATOR).status_code == 403  # release는 Admin


def test_teleop_flow_and_watchdog_zero(client):
    tc, svc = client
    assert tc.post("/api/v1/mode", json={"mode": "MANUAL"}, headers=OPERATOR).status_code == 200
    r = tc.post("/api/v1/teleop", json={"linear": 0.1, "angular": 0.0}, headers=OPERATOR)
    assert r.status_code == 200
    assert svc.command.select_output().linear == pytest.approx(0.1)
    svc.command.clear_manual()
    assert svc.command.select_output().linear == 0.0


def test_safety_stop_release_cycle(client):
    tc, svc = client
    assert tc.post("/api/v1/safety/stop", headers=VIEWER).status_code == 200   # 누구나 (SAF-001)
    assert svc.safety.estop is True
    assert svc.command.teleop(0.1, 0.0)[0] is False                            # 차단 확인
    assert tc.post("/api/v1/safety/release", headers=ADMIN).status_code == 200
    assert svc.safety.estop is False
    types = [e.type for e in svc.events.history()]
    assert "safety.estop" in types and "safety.estop_released" in types


def test_waypoints_crud_and_goal(client):
    tc, svc = client
    wp = {"name": "zone_a", "x": 1.5, "y": 2.5, "yaw": 0.0, "map_id": None, "metadata": {}}
    assert tc.post("/api/v1/waypoints", json=wp, headers=OPERATOR).status_code == 201
    dup = tc.post("/api/v1/waypoints", json=wp, headers=OPERATOR)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "WAYPOINT_EXISTS"

    class LocalExecutor:
        sent = []

        def send_goal(self, spec):
            LocalExecutor.sent.append(spec)

        def cancel_goal(self):
            pass

        def send_initial_pose(self, *a):
            pass

    svc.nav.executor = LocalExecutor()
    r = tc.post("/api/v1/navigation/goal", json={"waypoint": "zone_a"}, headers=OPERATOR)
    assert r.status_code == 200
    assert LocalExecutor.sent[0].x == 1.5
    missing = tc.post("/api/v1/navigation/goal", json={"waypoint": "ghost"}, headers=OPERATOR)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


def test_events_since_seq(client):
    tc, svc = client
    svc.events.publish("nav.completed")
    svc.events.publish("safety.watchdog")
    r = tc.get("/api/v1/events", headers=VIEWER).json()
    assert r["last_seq"] >= 2
    r2 = tc.get("/api/v1/events", params={"since_seq": r["last_seq"] - 1}, headers=VIEWER).json()
    assert len(r2["events"]) == 1


def test_error_shape_err101(client):
    tc, _ = client
    r = tc.post("/api/v1/teleop", json={"linear": 1.0}, headers=VIEWER)
    body = r.json()
    assert set(body.keys()) == {"error"}
    assert {"code", "message", "detail"} <= set(body["error"].keys())   # ERR-101
