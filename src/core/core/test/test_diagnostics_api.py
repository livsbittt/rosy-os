"""DIAG-001 진단 조회.

계약에는 v1.0 부터 있었지만 라우트가 없었고, 진단은 `/metrics` 와 상태
스냅샷으로만 나갔다. 여기서 가장 중요한 성질은 값이 존재한다는 것이 아니라
**`/metrics` 와 같은 값을 보인다**는 것이다 — 두 화면이 다른 건강 상태를
보이면 운영자는 어느 쪽도 믿을 수 없다.
"""

from __future__ import annotations

import re

import pytest
from core_common.protocol.schemas import HealthState

VIEWER = {"Authorization": "Bearer rosy-dev-viewer"}
ADMIN = {"Authorization": "Bearer rosy-dev-admin"}


@pytest.fixture
def client(core_client):
    return core_client()


def seed(svc):
    """브리지가 1 Hz 로 하는 일을 손으로 한 번 한다."""
    svc.state.set_diagnostic("core", HealthState.OK)
    svc.state.set_diagnostic("cpu", HealthState.WARNING)
    svc.state.set_diagnostic("odom_topic", HealthState.ERROR)


def test_the_list_reports_every_component_the_collector_knows(client):
    tc, svc = client
    seed(svc)

    body = tc.get("/api/v1/diagnostics", headers=VIEWER).json()

    assert body["components"] == {
        "core": "OK", "cpu": "WARNING", "odom_topic": "ERROR",
    }


def test_the_rollup_is_the_worst_component_not_the_first(client):
    tc, svc = client
    seed(svc)

    assert tc.get("/api/v1/diagnostics", headers=VIEWER).json()["health"] == "ERROR"

    svc.state.set_diagnostic("odom_topic", HealthState.OK)
    assert tc.get("/api/v1/diagnostics", headers=VIEWER).json()["health"] == "WARNING"


def test_an_empty_collector_reports_unknown_not_ok(client):
    """아직 아무것도 수집하지 않은 상태를 '정상'으로 보이면 안 된다."""
    tc, _svc = client

    body = tc.get("/api/v1/diagnostics", headers=VIEWER).json()

    assert body["components"] == {}
    assert body["health"] == "UNKNOWN"


def test_a_single_component_is_readable(client):
    tc, svc = client
    seed(svc)

    body = tc.get("/api/v1/diagnostics/cpu", headers=VIEWER).json()

    assert body == {"component": "cpu", "health": "WARNING"}


def test_control_adapter_readback_is_admin_only_and_secret_free(client):
    tc, svc = client

    class Adapter:
        enabled = True
        revision = "worker-v1"
        calibration_revision = 4
        calibration_digest = "a" * 64

    svc.control_adapter = Adapter()

    response = tc.get("/api/v1/diagnostics/control-adapter", headers=ADMIN)
    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "policy_revision": "worker-v1",
        "calibration_revision": 4,
        "calibration_digest": "a" * 64,
    }
    assert tc.get("/api/v1/diagnostics/control-adapter", headers=VIEWER).status_code == 403


def test_an_unknown_component_is_404_not_an_invented_ok(client):
    tc, svc = client
    seed(svc)

    response = tc.get("/api/v1/diagnostics/nonesuch", headers=VIEWER)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_diagnostics_need_a_token(client):
    tc, svc = client
    seed(svc)

    assert tc.get("/api/v1/diagnostics").status_code == 401
    assert tc.get("/api/v1/diagnostics/cpu").status_code == 401
    assert tc.get("/api/v1/diagnostics", headers=VIEWER).status_code == 200


def test_the_endpoint_and_metrics_agree_component_by_component(client):
    """DIAG-001 과 OBS-101 은 같은 출처를 읽어야 한다."""
    tc, svc = client
    seed(svc)
    numeric = {"OK": "0", "UNKNOWN": "1", "WARNING": "2", "ERROR": "3"}

    listed = tc.get("/api/v1/diagnostics", headers=VIEWER).json()["components"]
    metrics = tc.get("/metrics").text

    scraped = dict(re.findall(r'rosy_diagnostics_health\{component="([^"]+)"\} (\d)', metrics))
    assert scraped, "the metrics endpoint published no component health"
    assert set(scraped) == set(listed)
    for component, health in listed.items():
        assert scraped[component] == numeric[health], component
