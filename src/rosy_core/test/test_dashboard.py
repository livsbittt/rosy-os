from types import SimpleNamespace
from pathlib import Path

import pytest

from rosy_core.api.app import create_app


WEB_ROOT = Path(__file__).parent.parent / "rosy_core" / "web"


@pytest.fixture
def dashboard_client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    return TestClient(create_app({}, SimpleNamespace()))


def test_dashboard_shell_is_served_with_accessible_landmarks(dashboard_client):
    response = dashboard_client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'lang="ko"' in response.text
    assert "Rosy OS" in response.text
    assert "<main" in response.text
    assert 'aria-label="Rosy OS 상태"' in response.text
    assert 'data-mode="NAVIGATION" disabled' in response.text
    assert "https://" not in response.text


def test_dashboard_assets_are_local_and_reference_runtime_contract(dashboard_client):
    css = dashboard_client.get("/dashboard/assets/styles.css")
    script = dashboard_client.get("/dashboard/assets/app.js")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert "--signal-danger" in css.text
    assert "prefers-reduced-motion" in css.text

    assert script.status_code == 200
    assert "sessionStorage" in script.text
    assert "runtime_mode" in script.text
    assert "localStorage" not in script.text
    assert "/api/v1/system/runtime" in script.text
    assert "/api/v1/robot/state" in script.text
    assert "/api/v1/safety/stop" in script.text
    assert "/ws/state" in script.text
    assert "modeChangePending" in script.text
    assert "window.confirm" in script.text
    assert "navigation?.goal_navigation" in script.text
    assert "/api/v1/teleop" in script.text
    assert "pointerdown" in script.text
    assert "pointerup" in script.text
    assert "pointercancel" in script.text
    assert "pointerleave" in script.text
    assert "visibilitychange" in script.text
    assert "pagehide" in script.text
    assert "window.addEventListener(\"blur\"" in script.text
    assert "sendTeleop(0, 0, true)" in script.text
    assert "teleopIntervalMs: 100" in script.text


def test_dashboard_requires_local_bench_acknowledgement_for_motion():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="bench-safety-confirmed"' in html
    assert 'data-teleop="forward"' in html
    assert 'data-teleop="backward"' in html
    assert 'data-teleop="left"' in html
    assert 'data-teleop="right"' in html
    assert "누르고 있는 동안만" in html


def test_dashboard_motion_fails_to_zero_on_release_and_page_loss():
    script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

    assert "/api/v1/teleop" in script
    assert "sendTeleop(0, 0, true)" in script
    assert "pointerdown" in script
    assert "pointerup" in script
    assert "pointercancel" in script
    assert "pointerleave" in script
    assert "visibilitychange" in script
    assert "pagehide" in script
    assert 'window.addEventListener("blur"' in script
    assert "teleopIntervalMs: 100" in script
    assert "teleopPending" in script
    assert "AbortController" not in script
    assert "immediateZero" in script


def test_dashboard_html_cannot_bypass_security_headers_through_assets(dashboard_client):
    response = dashboard_client.get("/dashboard/assets/index.html")

    assert response.status_code == 404

    dashboard = dashboard_client.get("/dashboard")
    assert "frame-ancestors 'none'" in dashboard.headers["content-security-policy"]


def test_root_redirects_to_operator_dashboard(dashboard_client):
    response = dashboard_client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/dashboard"


def test_dashboard_asset_directory_is_an_explicit_python_package():
    assert (WEB_ROOT / "__init__.py").is_file()


def test_dashboard_exposes_ros_domain_bandwidth_and_topology_panel():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    css = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "ros-network-panel",
        "ros-domain-id",
        "dds-isolation",
        "ros-node-count",
        "ros-topic-count",
        "network-rx-rate",
        "network-tx-rate",
        "network-sparkline-rx",
        "network-sparkline-tx",
        "ros-graph-map",
        "ros-risk-list",
    ):
        assert f'id="{element_id}"' in html

    assert 'aria-label="ROS 노드와 토픽 연결 지도"' in html
    assert "renderRosNetwork" in script
    assert "renderSparkline" in script
    assert "renderRosGraph" in script
    assert "networkHistory" in script
    assert "runtime.ros" in script
    assert "createElementNS" in script
    assert "https://" not in script
    assert ".ros-network-panel" in css
    assert ".ros-graph-map" in css


def test_dashboard_draws_occupancy_map_path_and_click_goal():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    app = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    mapper = (WEB_ROOT / "map.js").read_text(encoding="utf-8")
    css = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "field-map-panel", "map-canvas", "map-status", "map-empty", "map-legend",
    ):
        assert f'id="{element_id}"' in html
    assert 'aria-label="점유 격자 지도"' in html
    assert 'data-map-layer="occupancy"' in html
    assert 'data-map-layer="costmap"' in html
    assert 'data-map-layer="path"' in html
    assert "지도를 클릭하면" in html

    assert 'from "./map.js"' in app
    assert "createFieldMap" in app
    assert "putImageData" not in app

    assert "export function createFieldMap" in mapper
    assert "export function GridFrame" not in mapper
    assert "function GridFrame" in mapper
    assert "worldToCell" in mapper
    assert "sampleWorld" in mapper
    assert "/api/v1/map" in mapper
    assert "/api/v1/navigation/path" in mapper
    assert "/api/v1/map/costmap" in mapper
    assert "/api/v1/navigation/goal" in mapper
    assert "putImageData" in mapper
    assert "fitCanvas" in mapper
    assert "ResizeObserver" in mapper
    assert "refreshPath" in mapper
    assert "window.confirm" in mapper
    assert "https://" not in mapper
    assert "localStorage" not in mapper

    assert ".field-map-panel" in css
    assert ".map-stage" in css
    assert "#map-canvas" in css
    assert ".map-legend" in css
    assert ".map-empty" in css


def test_dashboard_serves_map_module(dashboard_client):
    response = dashboard_client.get("/dashboard/assets/map.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "createFieldMap" in response.text
