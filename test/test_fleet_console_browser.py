"""D-131 1단계 — 군집 제어 오버레이의 브라우저 렌더 계약 (옵트인).

ROSY_RUN_BROWSER_TESTS=1 로 실행한다. 가짜 API 응답(활성 대형 + 중재 대기 +
릴레이 단절 팔로워)으로 콘솔을 띄워, 후단이 주는 상태가 실제로 그려지는지
단언한다. mutation-proven: drawFormationOverlay/drawMediation 호출을 지우면
이 시험은 적색이어야 한다(test/ AGENTS 규정).
"""

from __future__ import annotations

import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ROSY_RUN_BROWSER_TESTS") != "1",
    reason="set ROSY_RUN_BROWSER_TESTS=1 to run the optional Chromium regression",
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "site" / "fleet" / "fleet" / "server" / "web"
#: D-129 — /ui/tokens.css 의 실체는 CORE 웹 자산의 단일 파일이다. fleet 사본은 없다.
CANONICAL_TOKENS = ROOT / "src" / "core" / "core_api_web" / "core_api_web" / "web" / "tokens.css"

MAP_GRID = {
    "map_id": "mock:1", "width": 40, "height": 40, "resolution": 0.05,
    "origin": {"x": 0.0, "y": 0.0, "yaw": 0.0}, "data": [20] * (40 * 40),
}


def _robot(robot_id: str, pose: dict, **extra) -> dict:
    row = {
        "robot_id": robot_id, "online": True, "goal": None, "queued": None,
        "yielding": None, "error": None,
        "state": {"robot_id": robot_id, "mode": "NAVIGATION", "navigation": "NAVIGATING",
                  "pose": pose, "battery": {"percent": 90}, "safety": {"estop": False}},
    }
    row.update(extra)
    return row


SNAPSHOT = {
    "fleet": {"name": "site", "online": 3, "total": 3},
    "robots": [
        _robot("rosy_01", {"x": 1.0, "y": 1.0, "yaw": 0.0},
               goal={"x": 1.5, "y": 1.0, "yaw": 0.0}),
        _robot("rosy_02", {"x": 0.45, "y": 1.0, "yaw": 0.0}),
        _robot("rosy_03", {"x": 0.45, "y": 0.4, "yaw": 0.0},
               queued={"x": 1.2, "y": 0.4, "yaw": 0.0, "blocked_by": "rosy_02",
                       "waiting_on": ["rosy_02"], "reason": "ROUTE_CONFLICT"}),
    ],
    "ts": 0.0,
}

FORMATION = {
    "active": True, "state": "RUNNING", "leader": "rosy_01",
    "formation": "COLUMN", "spacing": 0.6,
    "assignment": {"rosy_02": {"distance": 0.6, "lateral": 0.0},
                   "rosy_03": {"distance": 1.2, "lateral": 0.0}},
    "reason": None, "pending_triggers": [],
    "relay": {"paused": False, "leader_rx_hz": 9.8, "leader_age_s": 0.1,
              "leader_last_error": None,
              "follower_tx_hz": {"rosy_02": 4.8, "rosy_03": 0.0},
              "follower_connected": {"rosy_02": True, "rosy_03": False}},
}

API = {
    "/api/fleet/state": SNAPSHOT,
    "/api/fleet/map": MAP_GRID,
    "/api/fleet/formation": FORMATION,
}


@pytest.fixture()
def console_url():
    # index.html 의 절대 경로(/ui/tokens.css, /console/assets/*)를 웹 디렉터로 풀어 준다.
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def translate_path(self, path: str) -> str:
            if path == "/ui/tokens.css":
                return str(CANONICAL_TOKENS)
            if path.startswith("/console/assets/"):
                path = "/" + path[len("/console/assets/"):]
            return super().translate_path(path)

        def log_message(self, *args):  # 시험 출력을 조용히
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


def test_the_console_renders_what_swarm_control_says(console_url):
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def serve_api(route):
            path = urlparse(route.request.url).path
            body = API.get(path)
            if body is None:
                route.fulfill(status=404, json={"detail": "no such api"})
                return
            route.fulfill(status=200, json=body)

        page.route("**/api/**", serve_api)
        page.goto(console_url, wait_until="networkidle")
        # 슬롯 고스트: COLUMN 에서 두 팔로워의 자리가 그려진다.
        page.wait_for_function("() => (window.__swarmOverlay?.slots || 0) === 2", timeout=8000)
        # 중재: rosy_03 의 대기 미션은 rosy_02 로의 점선이 된다.
        page.wait_for_function("() => (window.__swarmOverlay?.mediation || 0) >= 1", timeout=8000)

        roster = page.inner_text("#roster")
        assert "끊김" in roster, "연결이 끊긴 팔로워의 증거 태그가 없다"
        assert "지연" not in roster, "정상 스트림(4.8 Hz)에 지연 태그가 붙었다 — 정상은 무색이어야 한다"
        assert "0.60m" in page.inner_text("#formation-detail"), "슬롯 요약이 사라졌다"

        assert not errors, f"페이지 오류: {errors}"
        shot = Path(os.environ.get("TEMP", "/tmp")) / "fleet_console_overlay.png"
        page.screenshot(path=str(shot))
        print(f"\nscreenshot: {shot}")
        browser.close()
