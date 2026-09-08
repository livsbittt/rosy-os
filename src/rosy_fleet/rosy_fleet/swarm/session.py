"""rosy_fleet.swarm.session — 대형 세션: 무장 → 릴레이 → 감시 → FOR-004.

- 무장은 **전부 아니면 전무**다. 하나라도 거절되면 이미 무장된 팔로워를 풀고 끝낸다.
  무장된 팔로워만 남기면 참조 프레임 하나에 달려나갈 준비가 된 채로 남는다.
- FOR-004 기본 정책 HOLD 는 릴레이를 멈추는 것이다(설계 §6.4, D-35 후보). 팔로워는
  SWM-004 로 스스로 자리를 지키고, 리더 항법만 취소한다.
- 재개는 운영자만 한다. 자동 재개는 SRS 가 금지한 자동 재시도다.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional, Sequence

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.formation.assignment import GreedyDistanceAssigner, SlotAssigner
from rosy_fleet.formation.geometry import (
    DEFAULT_SPACING,
    Formation,
    SlotOffset,
    slot_world_position,
    slots,
)
from rosy_fleet.swarm.relay import Relay
from rosy_fleet.swarm.transport import RobotApiError, RobotClient

log = logging.getLogger(__name__)

#: 이 이벤트 중 하나가 어느 로봇에서든 오면 정책을 적용한다 (FOR-004).
TRIGGERS = frozenset({"nav.stuck", "nav.failed", "nav.blocked", "swarm.aborted", "safety.estop"})
#: 구독 필터. `swarm.hold` 는 정보이고 트리거가 아니지만 로그에 남기기 위해 받는다.
EVENT_TYPES = ("nav.*", "swarm.*", "safety.estop")

_BACKOFF_FIRST_S = 0.1
_BACKOFF_MAX_S = 2.0


class SessionState(str, Enum):
    IDLE = "IDLE"
    ARMING = "ARMING"
    RUNNING = "RUNNING"
    HOLDING = "HOLDING"
    STOPPED = "STOPPED"


class HoldPolicy(str, Enum):
    HOLD = "HOLD"      # 릴레이 pause + 리더 navigation/cancel. 팔로워 follow 세션은 산다.
    ABORT = "ABORT"    # 전 팔로워 swarm/cancel + 리더 navigation/cancel. 세션 종료.


@dataclass
class FormationSpec:
    formation: Formation
    spacing: float = DEFAULT_SPACING
    grid_cols: int = 2
    max_speed: float = 0.15
    stream_timeout_ms: int = 1000


class SessionError(Exception):
    pass


class ArmingFailed(SessionError):
    def __init__(self, robot_id: str, code: str, message: str = "") -> None:
        super().__init__(f"{robot_id} refused follow: {code} {message}".strip())
        self.robot_id = robot_id
        self.code = code


class MapMismatch(SessionError):
    def __init__(self, map_ids: dict[str, Optional[str]]) -> None:
        super().__init__(f"robots are not on one map: {map_ids}")
        self.map_ids = map_ids


class FormationSession:
    def __init__(self, leader: RobotClient, followers: Sequence[RobotClient],
                 spec: FormationSpec, *,
                 assigner: Optional[SlotAssigner] = None,
                 policy: HoldPolicy = HoldPolicy.HOLD,
                 relay_factory: Callable[..., Relay] = Relay,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._leader = leader
        self._followers = list(followers)
        self.spec = spec
        self._assigner = assigner or GreedyDistanceAssigner()
        self._policy = policy
        self._relay_factory = relay_factory
        self._sleep = sleep
        self.state = SessionState.IDLE
        #: `(사유, robot_id)`. HOLDING/STOPPED 의 이유.
        self.reason: Optional[tuple[str, Optional[str]]] = None
        self.assignment: dict[str, SlotOffset] = {}
        self.relay: Optional[Relay] = None
        self._watchers: list[asyncio.Task] = []
        self._by_id = {r.robot_id: r for r in [leader, *followers]}

    # --- 운영자 명령 --------------------------------------------------------------

    async def start(self) -> None:
        if self.state is not SessionState.IDLE:
            raise SessionError(f"cannot start from {self.state.value}")
        self.state = SessionState.ARMING
        try:
            self.assignment = await self._arm(self.spec)
        except SessionError as exc:
            self.state = SessionState.STOPPED
            self.reason = (f"arming_failed:{exc}", getattr(exc, "robot_id", None))
            raise
        self.relay = self._relay_factory(self._leader, self._followers)
        await self.relay.start()
        for robot in [self._leader, *self._followers]:
            self._watchers.append(asyncio.create_task(self._watch(robot)))
        self.state = SessionState.RUNNING
        self.reason = None

    async def reform(self, spec: FormationSpec) -> None:
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            raise SessionError(f"cannot reform from {self.state.value}")
        assert self.relay is not None
        self.relay.pause()
        try:
            self.assignment = await self._arm(spec)
        except SessionError as exc:
            # 정책과 무관하게 끝낸다. 재무장된 팔로워는 _arm 이 이미 풀었고 나머지는 옛
            # 오프셋의 follow 세션을 쥐고 있다 — 그 위에 스트림을 다시 켜면 대형이 둘로
            # 갈린다. HOLD 로 두면 resume 이 그것을 그대로 살린다.
            await self._abort(f"reform_failed:{exc}", getattr(exc, "robot_id", None))
            raise
        self.spec = spec
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def resume(self) -> None:
        if self.state is not SessionState.HOLDING:
            return
        assert self.relay is not None
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def stop(self) -> None:
        for task in self._watchers:
            task.cancel()
        for task in self._watchers:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._watchers.clear()
        if self.relay is not None:
            await self.relay.stop()
        for follower in self._followers:
            try:
                await follower.swarm_cancel()
            except Exception as exc:  # 한 대가 안 받아도 나머지는 푼다
                log.warning("%s: swarm/cancel failed on stop: %s", follower.robot_id, exc)
        self.state = SessionState.STOPPED

    # --- 무장 ---------------------------------------------------------------------

    async def _arm(self, spec: FormationSpec) -> dict[str, SlotOffset]:
        leader_state = await self._leader.state()
        states = {f.robot_id: await f.state() for f in self._followers}

        map_ids = {self._leader.robot_id: leader_state.get("map_id"),
                   **{rid: s.get("map_id") for rid, s in states.items()}}
        known = {m for m in map_ids.values() if m}
        if len(known) > 1:
            # 로봇 쪽도 프레임마다 검사하지만(map_mismatch HOLD), 시작 전에 알 수 있는
            # 것을 시작 뒤에 알게 하지 않는다. 값이 없는 로봇은 판단 대상이 아니다.
            raise MapMismatch(map_ids)

        offsets = slots(spec.formation, len(self._followers), spec.spacing, grid_cols=spec.grid_cols)
        pose = leader_state.get("pose") or {}
        lx, ly, lyaw = float(pose.get("x", 0.0)), float(pose.get("y", 0.0)), float(pose.get("yaw", 0.0))
        slot_points = [slot_world_position(o, lx, ly, lyaw) for o in offsets]
        robot_points = {
            rid: (float((s.get("pose") or {}).get("x", 0.0)), float((s.get("pose") or {}).get("y", 0.0)))
            for rid, s in states.items()
        }
        chosen = self._assigner.assign(robot_points, slot_points)
        assignment = {rid: offsets[j] for rid, j in chosen.items()}

        armed: list[RobotClient] = []
        for follower in self._followers:
            offset = assignment[follower.robot_id]
            params = SwarmFollowParams(
                target_robot_id=self._leader.robot_id,
                distance=offset.distance, lateral=offset.lateral,
                max_speed=spec.max_speed, stream_timeout_ms=spec.stream_timeout_ms,
            )
            try:
                await follower.follow(params)
            except RobotApiError as exc:
                await self._disarm(armed)
                raise ArmingFailed(exc.robot_id, exc.code, exc.message) from exc
            except Exception as exc:
                await self._disarm(armed)
                raise ArmingFailed(follower.robot_id, "TRANSPORT", str(exc)) from exc
            armed.append(follower)
        return assignment

    async def _disarm(self, armed: Sequence[RobotClient]) -> None:
        for follower in armed:
            try:
                await follower.swarm_cancel()
            except Exception as exc:
                log.warning("%s: swarm/cancel failed while disarming: %s", follower.robot_id, exc)

    # --- FOR-004 감시 ------------------------------------------------------------

    async def _watch(self, robot: RobotClient) -> None:
        backoff = _BACKOFF_FIRST_S
        first = True
        while True:
            if not first:
                await self._reconcile(robot)
            first = False
            try:
                async for event in robot.events(EVENT_TYPES):
                    backoff = _BACKOFF_FIRST_S
                    await self._handle_event(robot.robot_id, event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("%s: events socket error: %s", robot.robot_id, exc)
            # 조용히 닫혔든 예외였든 같은 backoff 다. 로봇이 꺼져 있으면 events() 는
            # 조용히 끝나므로, 여기서 기다리지 않으면 꺼진 로봇을 향해 빈 루프를 돈다.
            await self._sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX_S)

    async def _reconcile(self, robot: RobotClient) -> None:
        """이벤트 소켓이 끊긴 동안의 이벤트는 놓쳤다. 팔로워가 대형을 떠났는지 직접 본다."""
        if self.state is not SessionState.RUNNING or robot is self._leader:
            return
        try:
            swarm_state = await robot.swarm_state()
        except Exception as exc:
            log.warning("%s: swarm/state unavailable after reconnect: %s", robot.robot_id, exc)
            return
        if not swarm_state.get("active"):
            await self._apply_policy("swarm.aborted", robot.robot_id)

    async def _handle_event(self, robot_id: str, event: dict) -> None:
        type_ = str(event.get("type", ""))
        if type_ == "swarm.hold":
            # 정보다. 릴레이가 멈춰 있으면 우리가 만든 것이고, 아니면 로봇 쪽이 이미 서 있다.
            log.info("%s: swarm.hold %s", robot_id, (event.get("data") or {}).get("reason"))
            return
        if self.state is not SessionState.RUNNING:
            return
        if type_ in TRIGGERS:
            await self._apply_policy(type_, robot_id)

    async def _apply_policy(self, reason: str, robot_id: Optional[str]) -> None:
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            return
        assert self.relay is not None
        if self._policy is HoldPolicy.HOLD:
            # 상태를 먼저 바꾼다 — 아래 await 사이에 들어오는 이벤트는 무시돼야 한다.
            self.relay.pause()
            self.state = SessionState.HOLDING
            self.reason = (reason, robot_id)
            await self._cancel_leader()
            return
        await self._abort(reason, robot_id)

    async def _abort(self, reason: str, robot_id: Optional[str]) -> None:
        """ABORT 정책, 그리고 reform 실패: 전 팔로워를 풀고 릴레이를 끝내고 리더를 세운다."""
        self.state = SessionState.STOPPED
        self.reason = (reason, robot_id)
        if self.relay is not None:
            await self.relay.stop()
        await self._disarm(self._followers)
        await self._cancel_leader()

    async def _cancel_leader(self) -> None:
        try:
            await self._leader.navigation_cancel()
        except Exception as exc:
            log.warning("%s: navigation/cancel failed: %s", self._leader.robot_id, exc)
