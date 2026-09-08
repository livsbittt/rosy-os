"""rosy_fleet.swarm.session — 대형 세션: 무장 → 릴레이 → 감시 → FOR-004.

- 무장은 **전부 아니면 전무**다. 하나라도 거절되면 이미 무장된 팔로워를 풀고 끝낸다.
  무장된 팔로워만 남기면 참조 프레임 하나에 달려나갈 준비가 된 채로 남는다.
- FOR-004 기본 정책 HOLD 는 릴레이를 멈추는 것이다(설계 §6.4, D-35 후보). 팔로워는
  SWM-004 로 스스로 자리를 지키고, 리더 항법만 취소한다.
- 재개는 운영자만 한다. 자동 재개는 SRS 가 금지한 자동 재시도다.
- HOLDING 중에 온 트리거는 버리지 않고 `pending_triggers` 에 쌓는다. 그것이 남아
  있으면 `resume()` 은 거절한다 — 운영자는 `reform` 으로 다시 무장하거나 `stop` 한다.
  같은 `(사유, robot_id)` 는 한 번만 쌓는다. 끊긴 소켓은 2 s 마다 다시 열리므로
  그러지 않으면 같은 사고 하나가 목록을 끝없이 늘린다.
- `resume()` 도 `reform()` 도 await 여러 개짜리 구간이다. 그 사이에 감시가 돌고
  운영자가 `stop` 할 수 있다 — 릴레이를 만지기 직전에 무엇이 들어왔는지 다시 본다.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional, Sequence

from rosy_core.protocol.schemas import RobotMode, SwarmFollowParams
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
        follower_ids = [f.robot_id for f in followers]
        if len(set(follower_ids)) != len(follower_ids):
            # 릴레이도 같은 검사를 하지만 그때는 이미 팔로워가 무장돼 있다. 세션이 먼저 본다.
            raise ValueError(f"duplicate robot_id among followers: {follower_ids}")
        if leader.robot_id in follower_ids:
            raise ValueError(f"leader {leader.robot_id!r} cannot also be a follower")
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
        #: HOLDING 중에 온 트리거. 비어 있지 않으면 `resume()` 은 거절한다.
        self.pending_triggers: list[tuple[str, str]] = []
        self.assignment: dict[str, SlotOffset] = {}
        self.relay: Optional[Relay] = None
        self._watchers: list[asyncio.Task] = []
        #: 정책이 상태를 바꿀 때마다 오른다. `reform` 이 "무장 중에 무엇인가 걸렸다"를
        #: 이것으로 안다 — 무장은 await 여러 개짜리 구간이고 그 사이에 감시가 돈다.
        self._policy_seq = 0

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
        relay: Optional[Relay] = None
        try:
            relay = self._relay_factory(self._leader, self._followers)
            await relay.start()
        except Exception as exc:
            # 무장은 됐는데 스트림을 못 여는 상태가 가장 나쁘다 — 팔로워는 참조 프레임
            # 하나에 달려나갈 준비가 된 채로 남는다. 무장을 되돌리고 끝낸다.
            if relay is not None:
                try:
                    await relay.stop()
                except Exception as stop_exc:
                    log.warning("relay stop failed after a failed start: %s", stop_exc)
            await self._disarm(self._followers)
            self.state = SessionState.STOPPED
            self.reason = (f"relay_failed:{exc}", None)
            raise SessionError(f"relay could not be started: {exc}") from exc
        self.relay = relay
        for robot in [self._leader, *self._followers]:
            self._watchers.append(asyncio.create_task(self._watch(robot)))
        self.state = SessionState.RUNNING
        self.reason = None

    async def reform(self, spec: FormationSpec) -> None:
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            raise SessionError(f"cannot reform from {self.state.value}")
        assert self.relay is not None
        self.relay.pause()
        # 무장은 await 여러 개짜리 구간이다. 그 사이에 걸린 트리거를 재개가 지워서는 안 된다.
        seq = self._policy_seq
        carried = len(self.pending_triggers)
        try:
            assignment = await self._arm(spec)
        except SessionError as exc:
            if self.state is SessionState.STOPPED:
                await self._disarm(self._followers)
                raise SessionError(f"session aborted during reform: {self._reason_text()}") from exc
            # 정책과 무관하게 끝낸다. 재무장된 팔로워는 _arm 이 이미 풀었고 나머지는 옛
            # 오프셋의 follow 세션을 쥐고 있다 — 그 위에 스트림을 다시 켜면 대형이 둘로
            # 갈린다. HOLD 로 두면 resume 이 그것을 그대로 살린다.
            await self._abort(f"reform_failed:{exc}", getattr(exc, "robot_id", None))
            raise
        self.assignment = assignment
        self.spec = spec
        if self.state is SessionState.STOPPED:
            # 무장 도중 ABORT 가 걸렸다. 방금 무장한 팔로워들은 이미 죽은 릴레이를 보고
            # 있다 — 다시 푼다. 사유는 ABORT 쪽이 옳으므로 덮어쓰지 않는다.
            await self._disarm(self._followers)
            raise SessionError(f"session aborted during reform: {self._reason_text()}")
        # 이 reform 이 책임지는 몫은 시작 시점에 쌓여 있던 것까지다. 무장하는 동안 새로
        # 들어온 것은 아직 아무도 보지 않았다.
        self.pending_triggers = self.pending_triggers[carried:]
        if self._policy_seq != seq or self.pending_triggers:
            # 무장 도중 HOLD 가 걸렸다. 새 배정은 살리되 재개하지 않는다 — 운영자가 본다.
            if self.pending_triggers and self._policy_seq == seq:
                self.reason = self.pending_triggers[0]
            self.state = SessionState.HOLDING
            log.warning("reform finished but a trigger landed while arming: %s", self.reason)
            return
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def resume(self) -> None:
        if self.state is not SessionState.HOLDING:
            return
        assert self.relay is not None
        if self.pending_triggers:
            raise SessionError(
                f"cannot resume: unhandled triggers {self.pending_triggers}; "
                "reform to re-arm or stop")
        # 확인은 await 여러 개짜리 구간이다. 그 사이에 온 것을 재개가 덮어써서는 안 된다.
        seq = self._policy_seq
        carried = len(self.pending_triggers)
        for follower in self._followers:
            # HOLD 중에 팔로워가 대형을 떠났을 수 있다. 스트림만 다시 켜면 남은 팔로워만
            # 달려나간다 — 재개 전에 전원이 아직 따라오고 있는지 직접 본다.
            try:
                swarm_state = await follower.swarm_state()
            except Exception as exc:
                raise SessionError(
                    f"cannot resume: {follower.robot_id} swarm/state unavailable: {exc}") from exc
            if not swarm_state.get("active"):
                raise SessionError(
                    f"cannot resume: {follower.robot_id} is no longer following; "
                    "reform to re-arm or stop")
        await self._verify_resumable(seq, carried)
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def _verify_resumable(self, seq: int, carried: int) -> None:
        """재개 직전의 마지막 확인. 릴레이를 만지기 전에 이 구간 동안 무엇이 들어왔는지 본다."""
        try:
            leader_state = await self._leader.state()
        except Exception as exc:
            raise SessionError(
                f"cannot resume: {self._leader.robot_id} state unavailable: {exc}") from exc
        if leader_state.get("mode") == RobotMode.EMERGENCY.value:
            # 팔로워만 물어보면 리더가 선 채로 스트림이 다시 열린다.
            raise SessionError(
                f"cannot resume: {self._leader.robot_id} is in e-stop; clear it first")
        if self.state is not SessionState.HOLDING:
            raise SessionError(
                f"cannot resume: the session became {self.state.value} while it was being checked")
        if len(self.pending_triggers) != carried or self.pending_triggers:
            raise SessionError(
                f"cannot resume: {self.pending_triggers} arrived while it was being checked; "
                "reform to re-arm or stop")
        if self._policy_seq != seq:
            raise SessionError(
                f"cannot resume: the policy fired again while it was being checked "
                f"({self._reason_text()}); reform to re-arm or stop")

    async def stop(self) -> None:
        if self.state is SessionState.IDLE:
            # 무장도 릴레이도 감시도 없다. 끌 것이 없다.
            self.state = SessionState.STOPPED
            return
        await self._cancel_watchers()
        self._watchers.clear()
        await self._stop_relay()
        for follower in self._followers:
            try:
                await follower.swarm_cancel()
            except Exception as exc:  # 한 대가 안 받아도 나머지는 푼다
                log.warning("%s: swarm/cancel failed on stop: %s", follower.robot_id, exc)
        self.state = SessionState.STOPPED

    # --- 무장 ---------------------------------------------------------------------

    async def _arm(self, spec: FormationSpec) -> dict[str, SlotOffset]:
        leader_state = await self._leader.state()
        if leader_state.get("mode") == RobotMode.EMERGENCY.value:
            # 팔로워를 리더에 묶는 것이 무장이다. 선 리더에 묶으면 e-stop 이 풀리는 순간
            # 전원이 그 프레임을 따라간다 — 한 대도 묶기 전에 거절한다.
            raise ArmingFailed(self._leader.robot_id, "EMERGENCY_ACTIVE", "leader is in e-stop")
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
            if self.state is SessionState.STOPPED:
                # 무장하는 동안 세션이 끝났다. 죽은 릴레이를 보는 팔로워를 더 만들지 않는다.
                await self._disarm(armed)
                raise SessionError("session stopped while arming")
            offset = assignment[follower.robot_id]
            params = SwarmFollowParams(
                target_robot_id=self._leader.robot_id,
                distance=offset.distance, lateral=offset.lateral,
                max_speed=spec.max_speed, stream_timeout_ms=spec.stream_timeout_ms,
            )
            try:
                await follower.follow(params)
            except RobotApiError as exc:
                # 거절이다 — 이 로봇은 무장되지 않았다.
                await self._disarm(armed)
                raise ArmingFailed(exc.robot_id, exc.code, exc.message) from exc
            except Exception as exc:
                # 결과를 모른다. 타임아웃 뒤에 로봇이 follow 를 받아 놓았을 수 있으므로
                # 이 로봇도 함께 푼다 — 무장된 채 잊히는 것보다 두 번 푸는 것이 낫다.
                await self._disarm([*armed, follower])
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
        while self.state is not SessionState.STOPPED:
            if not first:
                await self._reconcile(robot)
                if self.state is SessionState.STOPPED:
                    return
            first = False
            try:
                async for event in robot.events(EVENT_TYPES):
                    backoff = _BACKOFF_FIRST_S
                    await self._handle_event(robot.robot_id, event)
                    if self.state is SessionState.STOPPED:
                        return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("%s: events socket error: %s", robot.robot_id, exc)
            if self.state is SessionState.STOPPED:
                return
            # 조용히 닫혔든 예외였든 같은 backoff 다. 로봇이 꺼져 있으면 events() 는
            # 조용히 끝나므로, 여기서 기다리지 않으면 꺼진 로봇을 향해 빈 루프를 돈다.
            await self._sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX_S)

    async def _cancel_watchers(self) -> None:
        """감시를 끝낸다. 자기 자신은 취소하지 않는다 — 그 태스크는 상태 검사로 나간다."""
        current = asyncio.current_task()
        cancelled = [task for task in self._watchers if task is not current]
        # 목록에는 살아 있는 감시만 남긴다. 두 번 부르는 abort→stop 이 끝난 태스크를
        # 다시 await 하지 않게, 그리고 "남은 감시"를 묻는 쪽이 참을 보게.
        self._watchers = [task for task in self._watchers if task is current]
        for task in cancelled:
            task.cancel()
        for task in cancelled:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                # 삼키면 감시가 왜 죽었는지 아무도 모른다.
                log.error("watcher task ended with an error: %r", exc)

    async def _reconcile(self, robot: RobotClient) -> None:
        """이벤트 소켓이 끊긴 동안의 이벤트는 놓쳤다. 로봇이 대형을 떠났는지 직접 본다."""
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            return
        if robot is self._leader:
            try:
                state = await self._leader.state()
            except Exception as exc:
                log.warning("%s: state unavailable after reconnect: %s", robot.robot_id, exc)
                return
            if state.get("mode") == RobotMode.EMERGENCY.value:
                # 리더의 e-stop 이벤트를 놓쳤다. 팔로워는 리더를 따라갈 준비가 돼 있다.
                await self._trigger("safety.estop", robot.robot_id)
            return
        try:
            swarm_state = await robot.swarm_state()
        except Exception as exc:
            log.warning("%s: swarm/state unavailable after reconnect: %s", robot.robot_id, exc)
            return
        if not swarm_state.get("active"):
            await self._trigger("swarm.aborted", robot.robot_id)

    async def _handle_event(self, robot_id: str, event: dict) -> None:
        type_ = str(event.get("type", ""))
        if type_ == "swarm.hold":
            self._log_hold(robot_id, event)
            return
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            return
        if type_ in TRIGGERS:
            await self._trigger(type_, robot_id)

    def _log_hold(self, robot_id: str, event: dict) -> None:
        # 릴레이가 멈춰 있거나 그 팔로워 소켓이 끊겨 있으면 우리가 만든 HOLD 다(정보).
        # 둘 다 아니면 로봇 쪽이 스스로 선 것이고, 그것은 우리가 모르는 이유다(경고).
        reason = (event.get("data") or {}).get("reason")
        ours = self.relay is None or self.relay.paused or not self.relay.is_connected(robot_id)
        (log.info if ours else log.warning)("%s: swarm.hold %s", robot_id, reason)

    async def _trigger(self, type_: str, robot_id: str) -> None:
        if self.state is SessionState.HOLDING:
            # 이미 서 있다고 해서 새 사고가 없던 일이 되지는 않는다. resume 이 이것을 본다.
            if (type_, robot_id) in self.pending_triggers:
                # 끊긴 소켓은 2 s 마다 다시 열리고 그때마다 같은 사실을 다시 말한다.
                # 같은 사고를 두 번 세면 목록만 끝없이 길어진다.
                log.debug("%s: %s while HOLDING (already pending)", robot_id, type_)
                return
            self.pending_triggers.append((type_, robot_id))
            log.warning("%s: %s while HOLDING — resume is blocked until reform or stop",
                        robot_id, type_)
            return
        await self._apply_policy(type_, robot_id)

    async def _apply_policy(self, reason: str, robot_id: Optional[str]) -> None:
        if self.state is not SessionState.RUNNING:
            return
        assert self.relay is not None
        if self._policy is HoldPolicy.HOLD:
            # 상태를 먼저 바꾼다 — 아래 await 사이에 들어오는 이벤트는 pending 으로 간다.
            self.relay.pause()
            self.state = SessionState.HOLDING
            self.reason = (reason, robot_id)
            self._policy_seq += 1
            await self._cancel_leader()
            return
        await self._abort(reason, robot_id)

    async def _abort(self, reason: str, robot_id: Optional[str]) -> None:
        """ABORT 정책, 그리고 reform 실패: 전 팔로워를 풀고 릴레이를 끝내고 리더를 세운다."""
        self.state = SessionState.STOPPED
        self.reason = (reason, robot_id)
        self._policy_seq += 1
        # 감시를 먼저 끝낸다. 끝난 세션의 소켓을 계속 다시 여는 감시는 유령이다.
        await self._cancel_watchers()
        # 릴레이를 못 끄는 것은 로봇을 무장한 채 두는 이유가 되지 못한다. 안전 작업이
        # 릴레이 뒤에 있으면, 릴레이가 던지는 순간 팔로워는 풀리지 않고 리더는 선다.
        await self._stop_relay()
        await self._disarm(self._followers)
        await self._cancel_leader()

    async def _stop_relay(self) -> None:
        if self.relay is None:
            return
        try:
            await self.relay.stop()
        except Exception as exc:
            log.error("relay stop failed: %s", exc)

    async def _cancel_leader(self) -> None:
        try:
            await self._leader.navigation_cancel()
        except Exception as exc:
            log.warning("%s: navigation/cancel failed: %s", self._leader.robot_id, exc)

    def _reason_text(self) -> str:
        if self.reason is None:
            return "unknown"
        why, robot_id = self.reason
        return f"{why} ({robot_id})" if robot_id else why
