"""릴레이·세션 테스트가 공유하는 가짜 전송계층.

`RobotClient` 프로토콜을 만족하되 네트워크는 없다. 스트림은 큐로 밀어 넣고,
`None` 을 넣으면 그 스트림은 끝난다(소켓 단절). 모든 호출은 `calls` 에 남는다.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional, Sequence

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.transport import RobotApiError

END = None


def run(coro):
    return asyncio.run(coro)


async def settle(rounds: int = 20) -> None:
    """대기 중인 태스크들이 한 바퀴씩 돌게 한다. 시간이 아니라 스케줄 회전이다."""
    for _ in range(rounds):
        await asyncio.sleep(0)


class FakeSink:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.fail_on_send = fail_on_send
        #: 잡혀 있으면 send 가 여기서 기다린다 — 느린 팔로워를 흉내낸다.
        self.gate: Optional[asyncio.Event] = None

    async def send(self, frame: str) -> None:
        if self.gate is not None:
            await self.gate.wait()
        if self.fail_on_send:
            raise ConnectionError("sink broke")
        self.sent.append(frame)

    async def close(self) -> None:
        self.closed = True


class FakeRobot:
    def __init__(self, robot_id: str, *, state: Optional[dict] = None,
                 follow_error: Optional[RobotApiError] = None,
                 swarm_state: Optional[dict] = None, log: Optional[list] = None) -> None:
        self.robot_id = robot_id
        self.calls: list[tuple] = []
        #: 여러 로봇의 호출 순서를 한 줄로 보고 싶을 때 같은 리스트를 넘긴다.
        self.log = log if log is not None else []
        self._state = state or {"robot_id": robot_id, "map_id": "m1",
                                "pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}
        self._swarm_state = swarm_state or {"active": True, "holding": False}
        self.follow_error = follow_error
        self.pose_frames: asyncio.Queue = asyncio.Queue()
        self.event_frames: asyncio.Queue = asyncio.Queue()
        self.sinks: list[FakeSink] = []
        #: 다음 open_reference_sink 가 이만큼 실패한다.
        self.sink_failures = 0
        self.next_sink_fail_on_send = False
        self.pose_opens = 0
        self.event_opens = 0
        #: 설정돼 있으면 pose_stream 이 열리자마자 이것을 raise 한다 (4401/4403 거부 흉내).
        self.pose_error = None

    def _record(self, *call) -> None:
        self.calls.append(call)
        self.log.append((self.robot_id,) + call)

    async def state(self) -> dict:
        self._record("state")
        return dict(self._state)

    async def swarm_state(self) -> dict:
        self._record("swarm_state")
        return dict(self._swarm_state)

    async def follow(self, params: SwarmFollowParams) -> dict:
        self._record("follow", params)
        if self.follow_error is not None:
            raise self.follow_error
        return {"role": "follower", "active": True}

    async def swarm_cancel(self) -> dict:
        self._record("swarm_cancel")
        return {"active": False}

    async def navigation_cancel(self) -> dict:
        self._record("navigation_cancel")
        return {"canceled": True}

    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict:
        self._record("navigation_goal", x, y, yaw)
        return {"accepted": True}

    async def pose_stream(self) -> AsyncIterator[str]:
        self.pose_opens += 1
        if self.pose_error is not None:
            await asyncio.sleep(0)
            raise self.pose_error
        while True:
            frame = await self.pose_frames.get()
            if frame is END:
                return
            # 실제 소켓은 프레임 사이에 제어권을 놓는다. 큐는 비어 있지 않으면 놓지
            # 않으므로 여기서 한 번 양보한다 — 아니면 N 프레임이 한 번에 처리돼
            # 깊이 1 큐가 그것을 하나로 합치고, "프레임마다 전달" 테스트가 거짓 실패한다.
            await asyncio.sleep(0)
            yield frame

    async def open_reference_sink(self) -> FakeSink:
        if self.sink_failures > 0:
            self.sink_failures -= 1
            raise ConnectionError("cannot open reference socket")
        sink = FakeSink(fail_on_send=self.next_sink_fail_on_send)
        self.next_sink_fail_on_send = False
        self.sinks.append(sink)
        return sink

    async def events(self, types: Sequence[str]) -> AsyncIterator[dict]:
        self.event_opens += 1
        self._record("events", tuple(types))
        while True:
            ev = await self.event_frames.get()
            if ev is END:
                return
            await asyncio.sleep(0)
            yield ev


class FakeRelay:
    """세션 테스트용. 실제 소켓 대신 호출 순서만 남긴다."""

    def __init__(self, leader, followers, *, log: Optional[list] = None, **_) -> None:
        self.leader = leader
        self.followers = list(followers)
        self.log = log if log is not None else []
        self.paused = False
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True
        self.log.append(("relay", "start"))

    async def stop(self) -> None:
        self.stopped = True
        self.log.append(("relay", "stop"))

    def pause(self) -> None:
        self.paused = True
        self.log.append(("relay", "pause"))

    def resume(self) -> None:
        self.paused = False
        self.log.append(("relay", "resume"))

    def is_connected(self, robot_id: str) -> bool:
        return True
