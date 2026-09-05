"""Optional browser-level safety test for ordered hold-to-drive shutdown."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "rosy_core" / "rosy_core" / "web"

pytestmark = pytest.mark.skipif(
    os.environ.get("ROSY_RUN_BROWSER_TESTS") != "1",
    reason="set ROSY_RUN_BROWSER_TESTS=1 to run the optional Chromium regression",
)

MAP_STUB = """
export function createFieldMap() {
  return { refresh: async () => ({}), setPose() {} };
}
"""

FETCH_INIT = """
sessionStorage.setItem('rosy.dashboard.token', 'operator-test-token');
window.__teleopCommands = [];
window.__apiCalls = [];
window.WebSocket = class extends EventTarget {
  constructor() { super(); setTimeout(() => this.dispatchEvent(new Event('open')), 0); }
  close() {}
};
window.fetch = async (input, options = {}) => {
  const path = new URL(typeof input === 'string' ? input : input.url, location.href).pathname;
  const method = (options.method || 'GET').toUpperCase();
  let parsed = null;
  if (options.body) {
    try { parsed = JSON.parse(options.body); } catch (_error) { parsed = options.body; }
  }
  window.__apiCalls.push({ method, path, body: parsed });
  const bodies = {
    '/api/v1/robot/state': {
      robot_id: 'rosy_01', online: true, mode: 'MANUAL', navigation: 'IDLE',
      pose: {x: 1.25, y: -0.5, yaw: 0.3}, velocity: {linear: 0, angular: 0},
      battery: {percent: 90, voltage: 7.5}, safety: {estop: false}, seq: 1,
    },
    '/api/v1/system/runtime': {
      os: {}, cpu: {}, memory: {}, storage: {},
      network: {throughput: {rx_bytes_per_second: null, tx_bytes_per_second: null}},
      ros: null,
    },
    '/api/v1/system/info': {name: 'Rosy', robot_id: 'rosy_01', hardware_model: 'test'},
    '/api/v1/system/capabilities': {
      teleop: true, slam: true, docking: {supported: false},
      navigation: {goal_navigation: true},
    },
    '/api/v1/safety/state': {
      estop: false, source: null, fleet_loss_policy: 'STOP',
      limits: {max_linear: 0.2, max_angular: 0.8, manual_linear: 0.15, manual_angular: 0.6},
      battery: {warning_percent: 20, critical_percent: 10, deep_percent: 5, critical_policy: 'RETURN_HOME'},
    },
    '/api/v1/events': {events: []},
    '/api/v1/waypoints': {waypoints: []},
    '/api/v1/docking/status': {state: 'UNDOCKED', dock_id: null, supported: false},
    '/api/v1/docking/docks': {docks: []},
    '/api/v1/host/network': {available: false, detail: 'no agent'},
    '/api/v1/host/release': {available: false, detail: 'no agent'},
    '/api/v1/host/commissioning': {runtime_mode: 'core', fleet_hold: true, detail: 'core'},
  };
  if (path === '/api/v1/teleop') {
    const command = JSON.parse(options.body);
    if (command.linear !== 0 || command.angular !== 0) {
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    window.__teleopCommands.push(command);
    return new Response(JSON.stringify({accepted: true}), {
      status: 200, headers: {'Content-Type': 'application/json'},
    });
  }
  if (method === 'POST' && path === '/api/v1/waypoints') {
    return new Response(JSON.stringify(parsed), {
      status: 201, headers: {'Content-Type': 'application/json'},
    });
  }
  if (method === 'PUT' && path === '/api/v1/safety/limits') {
    return new Response(JSON.stringify({
      estop: false, fleet_loss_policy: 'STOP',
      limits: {
        max_linear: 0.2, max_angular: 0.8,
        manual_linear: parsed.manual_linear, manual_angular: parsed.manual_angular,
      },
    }), { status: 200, headers: {'Content-Type': 'application/json'} });
  }
  if (method === 'POST' && path === '/api/v1/docking/types') {
    return new Response(JSON.stringify(parsed), {
      status: 200, headers: {'Content-Type': 'application/json'},
    });
  }
  if (method === 'POST' && path === '/api/v1/docking/docks') {
    return new Response(JSON.stringify(parsed), {
      status: 200, headers: {'Content-Type': 'application/json'},
    });
  }
  if (path === '/api/v1/logs/audit') {
    return new Response(JSON.stringify({events: []}), {
      status: 200, headers: {'Content-Type': 'application/json'},
    });
  }
  return new Response(JSON.stringify(bodies[path] ?? {}), {
    status: 200, headers: {'Content-Type': 'application/json'},
  });
};
"""


def _launch_page(playwright):
    launch_options = {"headless": True, "timeout": 10_000}
    if channel := os.environ.get("ROSY_BROWSER_CHANNEL"):
        launch_options["channel"] = channel
    browser = playwright.chromium.launch(**launch_options)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.set_default_timeout(5_000)
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    page.route(
        "http://rosy.test/dashboard",
        lambda route: route.fulfill(status=200, content_type="text/html", body=html),
    )
    page.route(
        "http://rosy.test/dashboard/assets/styles.css",
        lambda route: route.fulfill(status=200, content_type="text/css", body=""),
    )
    page.route(
        "http://rosy.test/dashboard/assets/app.js",
        lambda route: route.fulfill(
            status=200, content_type="application/javascript", body=script
        ),
    )
    page.route(
        "http://rosy.test/dashboard/assets/map.js",
        lambda route: route.fulfill(
            status=200, content_type="application/javascript", body=MAP_STUB
        ),
    )
    page.add_init_script(script=FETCH_INIT)
    page.on("dialog", lambda dialog: dialog.accept())
    return browser, page


def test_delayed_positive_request_cannot_arrive_after_release_zero():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser, page = _launch_page(playwright)
        except Exception as error:
            pytest.skip(f"Playwright Chromium unavailable: {error}")
        page.goto("http://rosy.test/dashboard", wait_until="domcontentloaded", timeout=5_000)
        assert page.locator("#network-rx-rate").inner_text() == "—"
        assert page.locator("#network-tx-rate").inner_text() == "—"
        assert "그래프 수집 불가" in page.locator("#ros-risk-list").inner_text()
        assert page.locator("#ros-risk-list .risk-clear").count() == 0
        page.locator("#bench-safety-confirmed").check()
        forward = page.locator('[data-teleop="forward"]')
        assert forward.is_enabled()

        forward.dispatch_event("pointerdown", {"pointerId": 1, "button": 0})
        page.wait_for_timeout(80)
        forward.dispatch_event("pointerup", {"pointerId": 1, "button": 0})
        page.wait_for_function("window.__teleopCommands.length >= 2")
        commands = page.evaluate("window.__teleopCommands")
        browser.close()

    assert commands[0] == {"linear": 0.05, "angular": 0}
    assert commands[-1] == {"linear": 0, "angular": 0}
    assert not any(command != {"linear": 0, "angular": 0} for command in commands[1:])


def test_field_settings_save_limits_waypoint_and_dock_without_navigation():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser, page = _launch_page(playwright)
        except Exception as error:
            pytest.skip(f"Playwright Chromium unavailable: {error}")
        page.goto("http://rosy.test/dashboard", wait_until="domcontentloaded", timeout=5_000)
        page.locator("#close-auth").click()
        page.locator("#field-settings-panel").scroll_into_view_if_needed()

        page.wait_for_function(
            "document.querySelector('#waypoint-list .empty-state')?.textContent?.includes('없습니다')"
        )
        page.wait_for_function(
            "document.getElementById('limits-save')"
            " && !document.getElementById('limits-save').disabled"
        )
        assert page.locator("#field-settings-panel").get_by_text("FLEET_HOLD", exact=True).count() == 1
        assert page.locator("#dock-capability").inner_text() == "HOLD"

        page.locator("#waypoint-name").fill("zone_a")
        page.locator("#waypoint-save").click()
        page.wait_for_function(
            "window.__apiCalls.some((c) => c.method === 'POST' && c.path === '/api/v1/waypoints')"
        )

        page.locator("#limit-manual-linear").fill("0.11")
        page.locator("#limit-manual-angular").fill("0.41")
        page.locator("#limits-save").click()
        page.wait_for_function(
            "window.__apiCalls.some((c) => c.method === 'PUT' && c.path === '/api/v1/safety/limits')"
        )
        assert "rosy.yaml" in page.locator("#limits-message").inner_text()

        page.locator("#dock-id").fill("dock_1")
        page.locator("#dock-register").click()
        page.wait_for_function(
            "window.__apiCalls.some((c) => c.method === 'POST' && c.path === '/api/v1/docking/docks')"
        )
        assert "등록" in page.locator("#dock-message").inner_text()
        assert page.url.startswith("http://rosy.test/dashboard")

        calls = page.evaluate("window.__apiCalls")
        browser.close()

    posts = {(call["method"], call["path"]) for call in calls}
    assert ("POST", "/api/v1/waypoints") in posts
    assert ("PUT", "/api/v1/safety/limits") in posts
    assert ("POST", "/api/v1/docking/types") in posts
    assert ("POST", "/api/v1/docking/docks") in posts
    waypoint = next(call for call in calls if call["path"] == "/api/v1/waypoints" and call["method"] == "POST")
    assert waypoint["body"]["name"] == "zone_a"
    assert waypoint["body"]["x"] == 1.25
    limits = next(call for call in calls if call["path"] == "/api/v1/safety/limits")
    assert limits["body"]["manual_linear"] == 0.11
    dock = next(call for call in calls if call["path"] == "/api/v1/docking/docks" and call["method"] == "POST")
    assert dock["body"]["id"] == "dock_1"
    assert dock["body"]["type"] == "rosy_v1"
