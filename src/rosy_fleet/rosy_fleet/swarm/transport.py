"""rosy_fleet.swarm.transport — 로봇 계약(API Ref)을 부르는 유일한 곳.

릴레이와 세션은 `RobotClient` 프로토콜만 본다. 테스트는 가짜를 끼우고, 운용은
`HttpRobotClient`(httpx + websockets) 를 끼운다. WS 이터레이터는 소켓이 닫히면
**조용히 끝난다** — 재연결은 호출자(릴레이/세션)의 정책이다.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional, Protocol, Sequence, runtime_checkable

import httpx

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.robots import RobotEndpoint, ws_url


class RobotApiError(Exception):
    """로봇이 4xx/5xx 를 돌려줬다. `code` 는 ERR-101 본문의 것, 없으면 `HTTP_<status>`."""

    def __init__(self, robot_id: str, status: int, code: str, message: str) -> None:
        super().__init__(f"{robot_id}: {code} ({status}) {message}")
        self.robot_id = robot_id
        self.status = status
        self.code = code
        self.message = message


class ReferenceSink(Protocol):
    async def send(self, frame: str) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class RobotClient(Protocol):
    robot_id: str

    async def state(self) -> dict: ...
    async def swarm_state(self) -> dict: ...
    async def follow(self, params: SwarmFollowParams) -> dict: ...
    async def swarm_cancel(self) -> dict: ...
    async def navigation_cancel(self) -> dict: ...
    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict: ...
    def pose_stream(self) -> AsyncIterator[str]: ...
    async def open_reference_sink(self) -> ReferenceSink: ...
    def events(self, types: Sequence[str]) -> AsyncIterator[dict]: ...


class _WebsocketSink:
    def __init__(self, ws) -> None:
        self._ws = ws

    async def send(self, frame: str) -> None:
        await self._ws.send(frame)

    async def close(self) -> None:
        await self._ws.close()


class HttpRobotClient:
    def __init__(self, endpoint: RobotEndpoint, *, http: Optional[httpx.AsyncClient] = None,
                 timeout_s: float = 5.0) -> None:
        self.robot_id = endpoint.robot_id
        self._ep = endpoint
        self._http = http or httpx.AsyncClient(base_url=endpoint.base_url, timeout=timeout_s)

    # --- REST -----------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ep.token}"}

    def _check(self, resp: httpx.Response) -> dict:
        if resp.status_code < 400:
            return resp.json() if resp.content else {}
        code, message = f"HTTP_{resp.status_code}", resp.text
        try:
            err = resp.json().get("error") or {}
            code = str(err.get("code") or code)
            message = str(err.get("message") or message)
        except (ValueError, AttributeError):
            pass
        raise RobotApiError(self.robot_id, resp.status_code, code, message)

    async def _get(self, path: str) -> dict:
        return self._check(await self._http.get(path, headers=self._headers()))

    async def _post(self, path: str, body: Optional[dict[str, Any]] = None) -> dict:
        return self._check(await self._http.post(path, json=body, headers=self._headers()))

    async def state(self) -> dict:
        return await self._get("/api/v1/robot/state")

    async def swarm_state(self) -> dict:
        return await self._get("/api/v1/swarm/state")

    async def follow(self, params: SwarmFollowParams) -> dict:
        return await self._post("/api/v1/swarm/follow", params.model_dump(mode="json"))

    async def swarm_cancel(self) -> dict:
        return await self._post("/api/v1/swarm/cancel")

    async def navigation_cancel(self) -> dict:
        return await self._post("/api/v1/navigation/cancel")

    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict:
        return await self._post("/api/v1/navigation/goal", {"x": x, "y": y, "yaw": yaw})

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- WS -------------------------------------------------------------------

    def pose_url(self) -> str:
        return ws_url(self._ep.base_url, "/ws/swarm/pose", self._ep.token)

    def reference_url(self) -> str:
        return ws_url(self._ep.base_url, "/ws/swarm/reference", self._ep.token)

    def events_url(self, types: Sequence[str]) -> str:
        return ws_url(self._ep.base_url, "/ws/events", self._ep.token, types=",".join(types))

    async def pose_stream(self) -> AsyncIterator[str]:
        """리더 pose 프레임(텍스트). 소켓이 닫히면 끝난다 — 재연결은 호출자 몫."""
        import websockets

        try:
            async with websockets.connect(self.pose_url()) as ws:
                async for frame in ws:
                    yield frame if isinstance(frame, str) else frame.decode("utf-8")
        except (OSError, websockets.exceptions.WebSocketException):
            return

    async def open_reference_sink(self) -> ReferenceSink:
        import websockets

        return _WebsocketSink(await websockets.connect(self.reference_url()))

    async def events(self, types: Sequence[str]) -> AsyncIterator[dict]:
        import websockets

        try:
            async with websockets.connect(self.events_url(types)) as ws:
                async for frame in ws:
                    try:
                        event = json.loads(frame)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(event, dict):
                        yield event
        except (OSError, websockets.exceptions.WebSocketException):
            return
