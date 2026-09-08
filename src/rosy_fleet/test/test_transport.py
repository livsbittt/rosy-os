"""HttpRobotClient — 로봇 REST 를 부르는 유일한 곳. 에러 본문은 ERR-101 형식이다."""

import asyncio
import json

import httpx
import pytest

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.swarm.transport import HttpRobotClient, RobotApiError, RobotClient

EP = RobotEndpoint("rosy_02", "http://robot:8080", "op-token")


def run(coro):
    return asyncio.run(coro)


def _client(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=EP.base_url)
    return HttpRobotClient(EP, http=http)


def test_it_satisfies_the_protocol():
    assert isinstance(_client(lambda r: httpx.Response(200, json={})), RobotClient)


def test_follow_posts_the_params_with_a_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"role": "follower", "active": True})

    params = SwarmFollowParams(target_robot_id="rosy_01", distance=0.6, lateral=-0.6,
                               max_speed=0.15, stream_timeout_ms=1000)
    got = run(_client(handler).follow(params))
    assert got["active"] is True
    assert seen["path"] == "/api/v1/swarm/follow"
    assert seen["auth"] == "Bearer op-token"
    assert seen["body"]["target_robot_id"] == "rosy_01"
    assert seen["body"]["lateral"] == -0.6
    assert seen["body"]["source"] == "fleet"


def test_an_error_body_becomes_a_robot_api_error_with_the_robots_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": {"code": "DOCKING_ACTIVE",
                                                   "message": "a docking run owns navigation",
                                                   "detail": None}})

    with pytest.raises(RobotApiError) as exc:
        run(_client(handler).follow(SwarmFollowParams(target_robot_id="rosy_01")))
    assert exc.value.robot_id == "rosy_02"
    assert exc.value.status == 409
    assert exc.value.code == "DOCKING_ACTIVE"


def test_a_non_json_error_still_raises_with_an_http_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(RobotApiError) as exc:
        run(_client(handler).state())
    assert exc.value.code == "HTTP_502"


@pytest.mark.parametrize("method, path", [
    ("state", "/api/v1/robot/state"),
    ("swarm_state", "/api/v1/swarm/state"),
    ("swarm_cancel", "/api/v1/swarm/cancel"),
    ("navigation_cancel", "/api/v1/navigation/cancel"),
])
def test_each_call_hits_its_route(method, path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx.Response(200, json={"ok": True})

    assert run(getattr(_client(handler), method)()) == {"ok": True}
    assert seen["path"] == path
    assert seen["method"] == ("GET" if method.endswith("state") else "POST")


def test_navigation_goal_posts_x_y_yaw():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"accepted": True})

    run(_client(handler).navigation_goal(1.0, 2.0, 0.5))
    assert seen["path"] == "/api/v1/navigation/goal"
    assert seen["body"] == {"x": 1.0, "y": 2.0, "yaw": 0.5}


def test_socket_urls_point_at_the_robot():
    c = _client(lambda r: httpx.Response(200, json={}))
    assert c.pose_url() == "ws://robot:8080/ws/swarm/pose?token=op-token"
    assert c.reference_url() == "ws://robot:8080/ws/swarm/reference?token=op-token"
    assert c.events_url(["nav.*", "swarm.*"]) == "ws://robot:8080/ws/events?token=op-token&types=nav.%2A%2Cswarm.%2A"
