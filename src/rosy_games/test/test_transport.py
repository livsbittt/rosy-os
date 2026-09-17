from __future__ import annotations

from pathlib import Path

import httpx

from rosy_games.field import Twist
from rosy_games.host.transport import HttpPlayerClient

SOURCE = Path(__file__).resolve().parents[1] / "rosy_games" / "host" / "transport.py"


def test_transport_source_has_only_mode_teleop_and_stop():
    text = SOURCE.read_text(encoding="utf-8")
    for banned in ("/follow", "/goal", "NavigateToPose"):
        assert banned not in text


def test_http_player_posts_manual_teleop_and_stop(tmp_path):
    calls: list[tuple[str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode() if request.content else None
        calls.append((str(request.url), body))
        if request.url.path.endswith("/mode") or request.url.path.endswith("/teleop") or request.url.path.endswith("/stop"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://robot")
    player = HttpPlayerClient("rosy_01", "http://robot", "secret", client=http)
    player.set_manual()
    player.teleop(Twist(0.08, 0.1))
    player.estop()
    paths = [httpx.URL(url).path for url, _ in calls]
    assert paths == ["/api/v1/mode", "/api/v1/teleop", "/api/v1/safety/stop"]
    assert "MANUAL" in (calls[0][1] or "")
    assert "0.08" in (calls[1][1] or "")


def test_http_4xx_raises_so_the_loop_can_estop_both():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no"})

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://robot")
    player = HttpPlayerClient("rosy_01", "http://robot", client=http)
    try:
        player.set_manual()
    except httpx.HTTPStatusError:
        return
    raise AssertionError("expected HTTPStatusError")
