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

def test_delayed_positive_request_cannot_arrive_after_release_zero():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")

    with sync_playwright() as playwright:
        try:
            launch_options = {"headless": True, "timeout": 10_000}
            if channel := os.environ.get("ROSY_BROWSER_CHANNEL"):
                launch_options["channel"] = channel
            browser = playwright.chromium.launch(**launch_options)
        except Exception as error:
            pytest.skip(f"Playwright Chromium unavailable: {error}")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.set_default_timeout(5_000)
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
        page.add_init_script(
            script="""
            sessionStorage.setItem('rosy.dashboard.token', 'operator-test-token');
            window.__teleopCommands = [];
            window.WebSocket = class extends EventTarget {
              constructor() { super(); setTimeout(() => this.dispatchEvent(new Event('open')), 0); }
              close() {}
            };
            window.fetch = async (input, options = {}) => {
              const path = new URL(typeof input === 'string' ? input : input.url, location.href).pathname;
              const bodies = {
                '/api/v1/robot/state': {
                  robot_id: 'rosy_01', online: true, mode: 'MANUAL', navigation: 'IDLE',
                  pose: {x: 0, y: 0, yaw: 0}, velocity: {linear: 0, angular: 0},
                  battery: {percent: 90, voltage: 7.5}, safety: {estop: false}, seq: 1,
                },
                '/api/v1/system/runtime': {os: {}, cpu: {}, memory: {}, storage: {}, network: {}},
                '/api/v1/system/info': {name: 'Rosy', robot_id: 'rosy_01', hardware_model: 'test'},
                '/api/v1/system/capabilities': {teleop: true, navigation: {goal_navigation: false}},
                '/api/v1/safety/state': {estop: false, source: null},
                '/api/v1/events': {events: []},
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
              return new Response(JSON.stringify(bodies[path] ?? {}), {
                status: 200, headers: {'Content-Type': 'application/json'},
              });
            };
            """
        )
        page.goto("http://rosy.test/dashboard", wait_until="domcontentloaded", timeout=5_000)
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
