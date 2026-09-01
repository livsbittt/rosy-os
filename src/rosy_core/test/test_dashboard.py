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
    assert "localStorage" not in script.text
    assert "/api/v1/system/runtime" in script.text
    assert "/api/v1/robot/state" in script.text
    assert "/api/v1/safety/stop" in script.text
    assert "/ws/state" in script.text


def test_root_redirects_to_operator_dashboard(dashboard_client):
    response = dashboard_client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/dashboard"


def test_dashboard_asset_directory_is_an_explicit_python_package():
    assert (WEB_ROOT / "__init__.py").is_file()
