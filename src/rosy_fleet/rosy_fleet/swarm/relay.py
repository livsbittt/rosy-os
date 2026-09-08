"""rosy_fleet.swarm.relay — 리더 pose 소켓 1 → 팔로워 reference 소켓 N (D-31).

규칙:
- 프레임을 바꾸지 않는다. 계측을 위해 파싱은 하되 전달하는 바이트는 그대로다.
- 합성하지 않는다. 리더가 끊기면 팔로워는 SWM-004 로 스스로 HOLD 한다. 마지막
  프레임을 반복하면 죽은 리더가 살아 있는 것으로 보인다.
- 팔로워 하나의 실패가 나머지를 막지 않는다. 소켓별 태스크, 소켓별 재연결.
- 느린 팔로워에 밀리지 않는다. 소켓별 큐는 깊이 1, 최신이 이전을 덮는다.
- `pause()` 중에는 리더를 계속 읽되 팔로워에 쓰지 않는다. FOR-004 의 "전체 HOLD"
  가 이것이다 (설계 §6.4, D-35 후보).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Sequence

from rosy_fleet.swarm.transport import RobotApiError, RobotClient

_BACKOFF_FIRST_S = 0.1
_RATE_WINDOW = 20


@dataclass
class RelayStats:
    leader_frames: int = 0
    leader_dropped: int = 0
    leader_rx_hz: float = 0.0
    #: 리더 소켓이 마지막으로 **거부**된 이유 (4401/4403 → RobotApiError 문자열). 재연결은
    #: 계속하지만, "0 Hz 가 영원히" 인 화면에 이유가 붙어야 한다. 프레임이 오면 None 으로 돈다.
    leader_last_error: Optional[str] = None
    paused: bool = False
    follower_tx: dict[str, int] = field(default_factory=dict)
    follower_tx_hz: dict[str, float] = field(default_factory=dict)
    follower_connected: dict[str, bool] = field(default_factory=dict)


class _Rate:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._stamps: deque[float] = deque(maxlen=_RATE_WINDOW)

    def tick(self) -> None:
        self._stamps.append(self._clock())

    def hz(self) -> float:
        if len(self._stamps) < 2:
            return 0.0
        span = self._stamps[-1] - self._stamps[0]
        return (len(self._stamps) - 1) / span if span > 0 else 0.0


class _Lane:
    """팔로워 하나. 깊이 1 큐 + 연결 상태 + 송신 계측."""

    def __init__(self, robot: RobotClient, clock: Callable[[], float]) -> None:
        self.robot = robot
        self.latest: Optional[str] = None
        self.wake = asyncio.Event()
        self.connected = False
        self.tx = 0
        self.rate = _Rate(clock)
        self.sink = None


class Relay:
    def __init__(self, leader: RobotClient, followers: Sequence[RobotClient], *,
                 clock: Callable[[], float] = time.monotonic,
                 reconnect_max_s: float = 2.0,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._leader = leader
        self._lanes = {f.robot_id: _Lane(f, clock) for f in followers}
        self._clock = clock
        self._reconnect_max = reconnect_max_s
        self._sleep = sleep
        self._paused = False
        self._tasks: list[asyncio.Task] = []
        self._leader_frames = 0
        self._leader_dropped = 0
        self._leader_rate = _Rate(clock)
        self._last_seq: Optional[int] = None
        self._leader_last_error: Optional[str] = None
        self._running = False

    # --- 수명 --------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._read_leader()))
        for lane in self._lanes.values():
            self._tasks.append(asyncio.create_task(self._feed(lane)))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        for lane in self._lanes.values():
            if lane.sink is not None:
                try:
                    await lane.sink.close()
                except Exception:
                    pass
                lane.sink = None
            lane.connected = False

    def pause(self) -> None:
        self._paused = True
        for lane in self._lanes.values():
            lane.latest = None   # 멈추기 전 프레임이 resume 뒤에 나가면 안 된다

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def is_connected(self, robot_id: str) -> bool:
        lane = self._lanes.get(robot_id)
        return bool(lane and lane.connected)

    def stats(self) -> RelayStats:
        return RelayStats(
            leader_frames=self._leader_frames,
            leader_dropped=self._leader_dropped,
            leader_rx_hz=self._leader_rate.hz(),
            leader_last_error=self._leader_last_error,
            paused=self._paused,
            follower_tx={rid: lane.tx for rid, lane in self._lanes.items()},
            follower_tx_hz={rid: lane.rate.hz() for rid, lane in self._lanes.items()},
            follower_connected={rid: lane.connected for rid, lane in self._lanes.items()},
        )

    # --- 리더 --------------------------------------------------------------------

    async def _read_leader(self) -> None:
        backoff = _BACKOFF_FIRST_S
        while self._running:
            got_any = False
            try:
                async for frame in self._leader.pose_stream():
                    got_any = True
                    backoff = _BACKOFF_FIRST_S
                    self._leader_last_error = None
                    self._on_frame(frame)
            except asyncio.CancelledError:
                raise
            except RobotApiError as exc:
                # 4401/4403: 토큰이나 capability 문제다. 재연결은 계속하되 이유를 남긴다 —
                # 조용히 0 Hz 로 도는 것이 이 릴레이의 가장 나쁜 실패다.
                self._leader_last_error = str(exc)
            except Exception:
                pass
            if not self._running:
                return
            # 소켓이 끝났다. 합성하지 않고 다시 연다.
            await self._sleep(backoff if not got_any else _BACKOFF_FIRST_S)
            backoff = min(backoff * 2, self._reconnect_max)

    def _on_frame(self, frame: str) -> None:
        self._leader_frames += 1
        self._leader_rate.tick()
        seq = _seq_of(frame)
        if seq is not None:
            if self._last_seq is not None and seq > self._last_seq + 1:
                self._leader_dropped += seq - self._last_seq - 1
            self._last_seq = seq
        if self._paused:
            return
        for lane in self._lanes.values():
            lane.latest = frame        # 깊이 1: 덮는다
            lane.wake.set()

    # --- 팔로워 ------------------------------------------------------------------

    async def _feed(self, lane: _Lane) -> None:
        backoff = _BACKOFF_FIRST_S
        while self._running:
            try:
                lane.sink = await lane.robot.open_reference_sink()
            except asyncio.CancelledError:
                raise
            except Exception:
                lane.connected = False
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._reconnect_max)
                continue
            lane.connected = True
            backoff = _BACKOFF_FIRST_S
            try:
                while self._running:
                    await lane.wake.wait()
                    lane.wake.clear()
                    frame, lane.latest = lane.latest, None
                    if frame is None:
                        continue
                    await lane.sink.send(frame)
                    lane.tx += 1
                    lane.rate.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                lane.connected = False
                try:
                    await lane.sink.close()
                except Exception:
                    pass
                lane.sink = None
                await self._sleep(backoff)


def _seq_of(frame: str) -> Optional[int]:
    try:
        payload = json.loads(frame).get("payload") or {}
        seq = payload.get("seq")
        return int(seq) if isinstance(seq, int) else None
    except (TypeError, ValueError, AttributeError):
        return None
