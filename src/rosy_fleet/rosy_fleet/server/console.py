"""사이트 오케스트레이터의 관제 표면 — 모음(gather)과 흩뿌림(scatter).

역할 경계는 [사이트 미들웨어 역할 패브릭 설계](../../../../docs/plans/2026-09-14-site-middleware-role-fabric-design.md)
§2 가 정한다. 이 모듈이 하는 일은 등록된 로봇의 상태를 모으고, 원자 액션
(goal / cancel / e-stop)을 내리는 것뿐이다. 하지 않는 일:

- 로봇 ROS 토픽 구독, `cmd_vel` 생산 — 최종 속도는 로봇 안 CORE 만 낸다 (D-59 §5).
- 미션 DSL 을 로봇에 내려보내기 — 미션은 Fleet 쪽에 남는다 (D-12).
- 로봇 로컬 대시보드를 대신하는 척하기 — 그쪽은 한 대의 현장 화면이다 (D-23).

**v1 의 gather 는 폴링이다.** 설계 §3 의 최종 모음 경로는 로봇 `FleetAgent` 가 여는
outbound WS(heartbeat/event)지만, 그 에이전트는 Fleet 서버가 생긴 뒤에야 소켓을 연다
(설계 §7 3단계). 그때까지는 같은 계약의 REST 상태를 주기적으로 읽는다. 읽기만 하므로
역할 경계는 같고, 에이전트가 붙으면 `snapshot()` 의 출처만 바뀐다.

전송은 `rosy_fleet.swarm.transport` 의 `RobotClient` 하나만 쓴다 — 로봇 계약을 부르는
자리는 거기 한 곳이다.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional, Sequence

from rosy_fleet.formation.geometry import DEFAULT_SPACING, Formation
from rosy_fleet.hub.hub import HubError, SiteHub
from rosy_fleet.server import traffic
from rosy_fleet.swarm.session import (
    FormationSession,
    FormationSpec,
    SessionError,
    SessionState,
)
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.swarm.transport import RobotApiError, RobotClient

#: 맵은 로봇마다 다시 받을 이유가 없다 — 한 사이트는 한 맵을 공유한다. 그래도 SLAM 으로
#: 맵이 바뀔 수 있으므로 무한정 붙들지는 않는다.
MAP_TTL_S = 10.0


def _error_of(exc: BaseException) -> dict:
    """예외를 UI 가 그대로 읽을 수 있는 모양으로. 로봇이 거절한 것과 닿지 못한 것을 가른다."""
    if isinstance(exc, RobotApiError):
        return {"reachable": True, "code": exc.code, "message": str(exc)}
    return {"reachable": False, "code": type(exc).__name__, "message": str(exc) or type(exc).__name__}


class FleetConsole:
    """robots.yaml 한 장에 적힌 N대를 하나의 관제 표면으로 묶는다."""

    def __init__(
        self,
        endpoints: Sequence[RobotEndpoint],
        clients: Sequence[RobotClient],
        *,
        clock: Callable[[], float] = time.monotonic,
        map_ttl_s: float = MAP_TTL_S,
        fleet_name: str = "rosy-site",
        clearance_m: float = traffic.DEFAULT_CLEARANCE_M,
        relay_factory=None,
    ) -> None:
        if len(endpoints) != len(clients):
            raise ValueError("endpoints and clients must line up one for one")
        self._clients: dict[str, RobotClient] = {
            ep.robot_id: client for ep, client in zip(endpoints, clients)
        }
        self._order = [ep.robot_id for ep in endpoints]
        self._clock = clock
        self._map_ttl_s = map_ttl_s
        self._map: Optional[dict] = None
        self._map_at = 0.0
        # 하달한 목표는 Fleet 이 기억한다. 로봇 상태 스냅샷에는 목표가 없고, 있어서도 안 된다
        # — 미션은 Fleet 쪽 개념이고 로봇은 원자 액션만 받는다 (D-12). 화면의 목표 표시는
        # "내가 무엇을 시켰는가"이지 로봇이 되돌려 준 값이 아니다.
        self._goals: dict[str, dict] = {}
        #: 달리는 로봇이 점유한 경로. 교행 판정의 재료이자, 왜 기다리는지의 근거다.
        self._claims: dict[str, list] = {}
        #: 남의 경로와 부딪혀 아직 못 내려간 미션. 앞이 비면 그대로 다시 내려간다.
        self._queued: dict[str, dict] = {}
        self._clearance_m = clearance_m
        #: 열려 있는 대형 세션. 한 사이트에 하나다 - 같은 로봇이 두 대형에 들어가면
        #: 어느 리더를 따라야 하는지 로봇 쪽에서 정할 방법이 없다.
        self._formation = None
        self._formation_leader = None
        #: 시험이 가짜 릴레이를 끼우는 자리. 운용에서는 None 이라 세션의 기본값을 쓴다.
        self._relay_factory = relay_factory
        self.fleet_name = fleet_name
        # e-stop 은 hub 의 scatter 를 그대로 쓴다 — 흩뿌림의 규칙을 두 군데 두지 않는다.
        self._hub = SiteHub(list(endpoints), dict(self._clients), fleet_name=fleet_name)

    @property
    def robot_ids(self) -> list[str]:
        return list(self._order)

    def _client(self, robot_id: str) -> RobotClient:
        client = self._clients.get(robot_id)
        if client is None:
            raise HubError("UNKNOWN_ROBOT", robot_id)
        return client

    # --- gather ---------------------------------------------------------------

    async def snapshot(self) -> dict:
        """N대 상태를 한 번에 모은다. 한 대가 죽어도 나머지는 그대로 온다."""
        results = await asyncio.gather(
            *(self._client(rid).state() for rid in self._order),
            return_exceptions=True,
        )
        robots = []
        for robot_id, result in zip(self._order, results):
            goal = self._goals.get(robot_id)
            queued = self._queued.get(robot_id)
            if isinstance(result, BaseException):
                robots.append({"robot_id": robot_id, "online": False, "goal": goal,
                               "queued": queued, "error": _error_of(result), "state": None})
            else:
                robots.append({"robot_id": robot_id, "online": True, "goal": goal,
                               "queued": queued, "error": None, "state": result})
        await self._run_traffic(robots)
        # 교통 정리가 대기 미션을 내려보냈으면 이 스냅샷이 이미 그 뒤다. 행을 다시 읽지
        # 않으면 화면은 방금 출발한 미션을 한 주기 동안 계속 "대기 중"으로 보여 준다.
        for row in robots:
            row["queued"] = self._queued.get(row["robot_id"])
            row["goal"] = self._goals.get(row["robot_id"])
        online = sum(1 for r in robots if r["online"])
        return {
            "fleet": {"name": self.fleet_name, "online": online, "total": len(robots)},
            "robots": robots,
            "ts": self._clock(),
        }

    async def map(self) -> Optional[dict]:
        """사이트가 공유하는 점유 격자. 응답한 첫 로봇 것을 쓰고 잠깐 물고 있는다.

        격자를 로봇마다 받아 오면 N배의 트래픽이 되고, 어차피 같은 맵이면 같은 그림이다.
        누구도 주지 못하면 `None` 이다 — UI 는 맵 없이도 목록을 띄워야 한다.
        """
        now = self._clock()
        if self._map is not None and now - self._map_at < self._map_ttl_s:
            return self._map
        for robot_id in self._order:
            try:
                grid = await self._client(robot_id).map()
            except Exception:
                continue
            if grid:
                self._map = grid
                self._map_at = now
                return grid
        return None

    # --- scatter --------------------------------------------------------------

    async def goal(self, robot_id: str, x: float, y: float, yaw: float = 0.0) -> dict:
        """한 대에 목표 하나. 로봇은 원자 액션만 받는다 (D-12).

        내려간 뒤 그 로봇의 계획 경로를 읽어, 이미 달리는 다른 로봇의 경로와 부딪히면
        취소하고 대기열에 넣는다. 경로는 목표를 받은 뒤에야 생기므로 순서가 이렇다 —
        되돌리는 비용은 로봇이 아직 거의 움직이지 않았을 때 취소 한 번이다.

        양보는 늘 **나중에 내려온 미션** 쪽이다. 달리던 로봇을 세우면 좁은 통로 한가운데
        멈춘 장애물이 하나 생길 뿐이고, 그 로봇이 비켜설 자리는 애초에 없다.
        """
        if robot_id in self._formation_members():
            # 팔로워는 리더 pose 를 따라가는 중이다. 여기에 목표를 따로 내리면 로봇 안에서
            # 두 임자가 같은 바퀴를 두고 다툰다 - 대형을 풀고 보내라고 돌려준다.
            raise HubError("FORMATION_ACTIVE",
                           f"{robot_id} is in the running formation; stop it first")
        result = await self._client(robot_id).navigation_goal(x, y, yaw)
        # 로봇이 받아들인 뒤에만 기억한다 — 거절된 목표가 화면에 남으면 운영자는 가지도
        # 않을 곳으로 로봇이 간다고 읽는다.
        self._goals[robot_id] = {"x": x, "y": y, "yaw": yaw}
        self._queued.pop(robot_id, None)

        route = await self._route_of(robot_id)
        blocker = traffic.blocking_robot(route, self._claims, self._clearance_m, skip=(robot_id,))
        if blocker is None:
            self._claims[robot_id] = route
            return result

        await self._client(robot_id).navigation_cancel()
        self._goals.pop(robot_id, None)
        self._claims.pop(robot_id, None)
        self._queued[robot_id] = {"x": x, "y": y, "yaw": yaw, "blocked_by": blocker}
        return {"accepted": True, "queued": True, "blocked_by": blocker}

    async def _route_of(self, robot_id: str) -> list:
        """계획 경로. 읽지 못하면 빈 목록이다 — 모른다는 이유로 미션을 막지 않는다."""
        try:
            return traffic.route_points(await self._client(robot_id).navigation_path())
        except Exception:
            return []

    async def _run_traffic(self, robots: list) -> None:
        """스냅샷마다 한 번: 끝난 로봇의 점유를 풀고, 풀린 자리의 대기 미션을 내려보낸다."""
        for row in robots:
            state = row.get("state") or {}
            if state.get("navigation") != "NAVIGATING":
                self._claims.pop(row["robot_id"], None)
        for robot_id in sorted(self._queued):
            mission = self._queued[robot_id]
            if mission["blocked_by"] in self._claims:
                continue
            self._queued.pop(robot_id, None)
            try:
                await self.goal(robot_id, mission["x"], mission["y"], mission["yaw"])
            except Exception:
                # 재하달이 실패하면 대기열에 되돌린다. 조용히 사라지면 운영자는 자기가
                # 내린 미션이 어디로 갔는지 알 수 없다.
                self._queued[robot_id] = mission

    async def cancel(self, robot_id: str) -> dict:
        result = await self._client(robot_id).navigation_cancel()
        self._goals.pop(robot_id, None)
        self._claims.pop(robot_id, None)
        self._queued.pop(robot_id, None)
        return result

    async def estop_all(self) -> dict:
        """전 대상 정지. 한 대가 거절해도 나머지에 계속 내린다.

        빨리 실패하면 안 된다 — 닿지 않는 한 대 때문에 멈출 수 있었던 나머지가 계속
        움직이는 것이 이 버튼에서 가장 나쁜 결과다. 로봇 쪽 e-stop 과 deadman 은 관제와
        무관하게 살아 있다(설계 §3).
        """
        # 대형이 살아 있으면 먼저 푼다. 릴레이가 참조를 계속 밀어 넣는 채로 로봇만 세우면,
        # e-stop 을 푸는 순간 팔로워가 밀린 참조를 향해 달려나간다.
        if self._formation is not None and self._formation_members():
            try:
                await self._formation.stop()
            except Exception:
                pass
            self._formation_leader = None
        results = await asyncio.gather(
            *(self._hub.scatter_estop(rid) for rid in self._order),
            return_exceptions=True,
        )
        rows = []
        for robot_id, result in zip(self._order, results):
            if isinstance(result, BaseException):
                # 이 대는 서지 않았다. 목표를 지우면 화면에서 "아무 데도 안 간다"로 보이지만
                # 실제로는 아직 가고 있을 수 있다 — 남겨 둔다.
                rows.append({"robot_id": robot_id, "stopped": False, "error": _error_of(result)})
            else:
                self._goals.pop(robot_id, None)
                self._claims.pop(robot_id, None)
                self._queued.pop(robot_id, None)
                rows.append({"robot_id": robot_id, "stopped": True, "result": result})
        return {"stopped": sum(1 for r in rows if r["stopped"]), "total": len(rows), "robots": rows}

    # --- 대형 (FOR-004) --------------------------------------------------------

    def _formation_members(self) -> set:
        """개별 미션을 받으면 안 되는 로봇 = 팔로워.

        **리더는 넣지 않는다.** 대형은 리더를 몰아서 움직이는 것이고(D-20: 오케스트레이션은
        Fleet, 폐루프 추종은 로봇), 리더가 목표를 못 받으면 대형은 무장만 된 채 아무 데도
        가지 못한다. 팔로워는 반대다 - 리더 pose 를 따라가는 중이라 목표를 따로 받으면
        로봇 안에서 두 임자가 같은 바퀴를 두고 다툰다.
        """
        session = self._formation
        if session is None or session.state in (SessionState.STOPPED, SessionState.IDLE):
            return set()
        return set(session.assignment)

    def formation_status(self) -> dict:
        """화면이 읽는 대형 상태. 세션이 없으면 `active: False` 하나다."""
        session = self._formation
        if session is None:
            return {"active": False, "state": "IDLE"}
        stats = session.relay.stats() if session.relay is not None else None
        return {
            "active": session.state in (SessionState.ARMING, SessionState.RUNNING,
                                        SessionState.HOLDING),
            "state": session.state.value,
            "leader": self._formation_leader,
            "formation": session.spec.formation.value,
            "spacing": session.spec.spacing,
            "assignment": {rid: {"distance": slot.distance, "lateral": slot.lateral}
                           for rid, slot in session.assignment.items()},
            # HOLDING 인데 이유가 비어 있으면 운영자는 왜 멈췄는지 알 길이 없다.
            "reason": list(session.reason) if session.reason else None,
            "pending_triggers": [list(t) for t in session.pending_triggers],
            "relay": None if stats is None else {
                "paused": stats.paused,
                "leader_rx_hz": round(stats.leader_rx_hz, 2),
                "leader_age_s": stats.leader_age_s,
                "leader_last_error": stats.leader_last_error,
                "follower_tx_hz": {k: round(v, 2) for k, v in stats.follower_tx_hz.items()},
                "follower_connected": dict(stats.follower_connected),
            },
        }

    def _spec(self, formation: str, spacing, max_speed) -> FormationSpec:
        try:
            shape = Formation(formation)
        except ValueError as exc:
            raise HubError("UNKNOWN_FORMATION", f"{formation} is not a formation") from exc
        current = self._formation.spec if self._formation is not None else None
        if max_speed is None:
            max_speed = current.max_speed if current is not None else 0.15
        return FormationSpec(
            formation=shape,
            spacing=DEFAULT_SPACING if spacing is None else spacing,
            max_speed=max_speed,
        )

    async def formation_start(self, leader_id: str, formation: str = "COLUMN",
                              spacing=None, max_speed=None) -> dict:
        """리더 하나와 나머지 전원으로 대형을 연다.

        이미 열려 있으면 거절한다. 조용히 갈아치우면 앞 세션의 팔로워가 무장된 채로
        남고, 그 로봇은 아무도 보내지 않는 참조를 기다리며 서 있게 된다.
        """
        if self._formation_members():
            raise HubError("FORMATION_ACTIVE", "a formation is already running; stop it first")
        leader = self._client(leader_id)
        followers = [self._clients[rid] for rid in self._order if rid != leader_id]
        if not followers:
            raise HubError("NO_FOLLOWERS", "a formation needs at least one follower")
        kwargs = {} if self._relay_factory is None else {"relay_factory": self._relay_factory}
        session = FormationSession(leader, followers,
                                   self._spec(formation, spacing, max_speed), **kwargs)
        self._formation = session
        self._formation_leader = leader_id
        try:
            await session.start()
        except SessionError as exc:
            # 세션이 자기 안에서 이미 무장을 되돌렸다. 상태는 남겨 화면이 이유를 읽게 한다.
            raise HubError("ARMING_FAILED", str(exc)) from exc
        return self.formation_status()

    async def formation_reform(self, formation: str, spacing=None) -> dict:
        session = self._formation
        if session is None or session.state is SessionState.STOPPED:
            raise HubError("NO_FORMATION", "no formation to reform")
        try:
            await session.reform(self._spec(formation, spacing, None))
        except SessionError as exc:
            raise HubError("REFORM_REFUSED", str(exc)) from exc
        return self.formation_status()

    async def formation_resume(self) -> dict:
        session = self._formation
        if session is None:
            raise HubError("NO_FORMATION", "no formation to resume")
        try:
            await session.resume()
        except SessionError as exc:
            raise HubError("RESUME_REFUSED", str(exc)) from exc
        return self.formation_status()

    async def formation_stop(self) -> dict:
        session = self._formation
        if session is None:
            return {"active": False, "state": "IDLE"}
        await session.stop()
        status = self.formation_status()
        self._formation_leader = None
        return status

    async def aclose(self) -> None:
        for client in self._clients.values():
            closer: Any = getattr(client, "aclose", None)
            if closer is not None:
                await closer()
