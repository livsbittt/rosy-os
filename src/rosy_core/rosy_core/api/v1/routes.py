"""rosy_core.api.v1 라우터 — API Ref §5 계약 구현 (P1-9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from rosy_core.api.deps import AuthContext, get_services, require_role
from rosy_core.api.errors import ApiError
from rosy_core.maps import valid_costmap_scope
from rosy_core.command.arbitration import Mode
from rosy_core.protocol.schemas import PowerMode, RobotMode
from rosy_core.docking.database import DockError, DockInstance, DockType
from rosy_core.services import CoreServices
from rosy_core.system.host_agent_client import HostAgentClient
from rosy_core.waypoints.manager import Waypoint

viewer = require_role("viewer")
operator = require_role("operator")
admin = require_role("administrator")

system_router = APIRouter(prefix="/api/v1/system", tags=["system"])


@system_router.get("/info")
def system_info(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return svc.identity.info()


@system_router.get("/capabilities")
def capabilities(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return svc.capability.to_dict()


@system_router.get("/runtime")
def system_runtime(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return svc.runtime_probe.snapshot()


robot_router = APIRouter(prefix="/api/v1/robot", tags=["robot"])


@robot_router.get("/state")
def robot_state(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return svc.state.snapshot().model_dump()


@robot_router.get("/pose")
def robot_pose(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    snap = svc.state.snapshot()
    return snap.pose.model_dump()


@robot_router.get("/battery")
def robot_battery(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    snap = svc.state.snapshot()
    return snap.battery.model_dump()


@robot_router.get("/velocity")
def robot_velocity(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    snap = svc.state.snapshot()
    return snap.velocity.model_dump()


control_router = APIRouter(prefix="/api/v1", tags=["control"])


class ModeRequest(BaseModel):
    mode: str = Field(pattern="^(IDLE|MANUAL|NAVIGATION)$")


class TeleopRequest(BaseModel):
    linear: float = 0.0
    angular: float = 0.0


@control_router.post("/mode")
def set_mode(body: ModeRequest, auth: AuthContext = Depends(operator),
             svc: CoreServices = Depends(get_services)):
    new_mode = Mode(body.mode)
    if new_mode is Mode.NAVIGATION:
        svc.capability.require("navigation.goal_navigation")
        if svc.modes.mode is not Mode.NAVIGATION:
            svc.command.clear_navigation()
    if new_mode is Mode.MANUAL and svc.nav.nav_state.value not in ("IDLE", "ARRIVED", "CANCELED", "FAILED"):
        svc.nav.cancel(source=f"mode:{auth.role}")
    ok, reason = svc.modes.transition(new_mode)
    if not ok:
        raise ApiError("MODE_CONFLICT", 409, reason)
    svc.state.set_mode(RobotMode(new_mode.value))
    svc.events.publish("mode.changed", source="api",
                       data={"from": "api", "to": new_mode.value, "by": auth.role})
    return {"mode": new_mode.value}


@control_router.post("/teleop")
def teleop(body: TeleopRequest, auth: AuthContext = Depends(operator),
           svc: CoreServices = Depends(get_services)):
    accepted, code = svc.command.teleop(body.linear, body.angular, source="manual")
    if not accepted:
        raise ApiError(code, 409 if code in ("MODE_CONFLICT", "EMERGENCY_ACTIVE") else 400,
                       f"teleop rejected: {code}")
    return {"accepted": True}


safety_router = APIRouter(prefix="/api/v1/safety", tags=["safety"])


@safety_router.post("/stop")
def safety_stop(auth: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    svc.modes.transition(Mode.EMERGENCY)
    svc.safety.trigger_estop(f"api:{auth.role}")
    svc.state.set_estop(True)
    return {"estop": True}


@safety_router.post("/release")
def safety_release(auth: AuthContext = Depends(admin), svc: CoreServices = Depends(get_services)):
    ok_mode, reason = svc.modes.release_emergency()
    if not ok_mode:
        raise ApiError("MODE_CONFLICT", 409, reason)
    svc.safety.release(by=f"api:{auth.role}")
    svc.state.set_estop(False)
    return {"estop": False}


@safety_router.get("/state")
def safety_state(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return {"estop": svc.safety.estop, "source": svc.safety.estop_source,
            "fleet_loss_policy": svc.safety.fleet_loss_policy,
            "limits": {"max_linear": svc.safety.limits.max_linear,
                       "max_angular": svc.safety.limits.max_angular,
                       "manual_linear": svc.safety.limits.manual_linear,
                       "manual_angular": svc.safety.limits.manual_angular}}


class LimitsRequest(BaseModel):
    manual_linear: float | None = None
    manual_angular: float | None = None


@safety_router.put("/limits")
def safety_limits(body: LimitsRequest, auth: AuthContext = Depends(admin),
                  svc: CoreServices = Depends(get_services)):
    if body.manual_linear is not None:
        svc.safety.limits.manual_linear = min(body.manual_linear, svc.safety.limits.max_linear)
    if body.manual_angular is not None:
        svc.safety.limits.manual_angular = min(body.manual_angular, svc.safety.limits.max_angular)
    svc.events.publish("config.changed", source="api", data={"key": "safety.limits"})
    return safety_state(svc)


navigation_router = APIRouter(prefix="/api/v1", tags=["navigation"])


class GoalRequest(BaseModel):
    x: float | None = None
    y: float | None = None
    yaw: float | None = 0.0
    waypoint: str | None = None


@navigation_router.post("/navigation/goal")
def navigation_goal(body: GoalRequest, auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    svc.capability.require("navigation.goal_navigation")
    spec = svc.nav.resolve_goal(x=body.x, y=body.y, yaw=body.yaw, waypoint=body.waypoint)
    svc.nav.goal(spec, source=f"api:{auth.role}")
    return {"accepted": True, "goal": {"x": spec.x, "y": spec.y, "yaw": spec.yaw}}


@navigation_router.post("/navigation/cancel")
def navigation_cancel(auth: AuthContext = Depends(operator),
                      svc: CoreServices = Depends(get_services)):
    svc.nav.cancel(source=f"api:{auth.role}")
    return {"navigation": svc.nav.nav_state.value}


@navigation_router.post("/navigation/home")
def navigation_home(auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    svc.capability.require("navigation.return_home")
    svc.nav.home(source=f"api:{auth.role}")
    return {"accepted": True}


@navigation_router.get("/navigation/state")
def navigation_state(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return {"navigation": svc.nav.nav_state.value, "map_id": svc.state.map_id}


@navigation_router.get("/navigation/path")
def navigation_path(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return {"poses": svc.maps.get_path()}


map_router = APIRouter(prefix="/api/v1/map", tags=["map"])


@map_router.get("")
def current_map(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    grid = svc.maps.get_map()
    if grid is None:
        raise ApiError("NOT_FOUND", 404, "no occupancy map received yet")
    return {"map_id": svc.state.map_id, **grid}


@map_router.get("/costmap")
def costmap(scope: str | None = Query(default=None),
            _: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    if scope is None or not valid_costmap_scope(scope):
        raise ApiError("VALIDATION_ERROR", 400, "scope must be global or local")
    grid = svc.maps.get_costmap(scope)
    if grid is None:
        raise ApiError("NOT_FOUND", 404, f"no {scope} costmap received yet")
    return {"scope": scope, **grid}


class InitialPoseRequest(BaseModel):
    x: float
    y: float
    yaw: float = 0.0


@navigation_router.post("/localization/initialpose")
def initialpose(body: InitialPoseRequest, auth: AuthContext = Depends(operator),
                svc: CoreServices = Depends(get_services)):
    svc.capability.require("navigation.goal_navigation")
    if svc.nav.executor is None:
        raise ApiError("CAPABILITY_NOT_SUPPORTED", 501, "localization executor unavailable")
    svc.nav.executor.send_initial_pose(body.x, body.y, body.yaw)
    svc.events.publish(
        "localization.initialpose",
        source=f"api:{auth.role}",
        data={"x": body.x, "y": body.y, "yaw": body.yaw},
    )
    return {"accepted": True}


waypoints_router = APIRouter(prefix="/api/v1/waypoints", tags=["waypoints"])


@waypoints_router.get("")
def list_waypoints(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return {"waypoints": [w.model_dump() for w in svc.waypoints.list()]}


@waypoints_router.post("", status_code=201)
def create_waypoint(body: Waypoint, auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    return svc.waypoints.create(body).model_dump()


@waypoints_router.put("/{name}")
def update_waypoint(name: str, body: dict, auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    return svc.waypoints.update(name, body).model_dump()


@waypoints_router.delete("/{name}", status_code=204)
def delete_waypoint(name: str, auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    svc.waypoints.delete(name)


events_router = APIRouter(prefix="/api/v1/events", tags=["events"])
logs_router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@events_router.get("")
def list_events(since_seq: int | None = None, limit: int = 100,
                _: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    events = svc.events.history(since_seq=since_seq, limit=limit)
    return {"events": [e.model_dump() for e in events], "last_seq": svc.events.last_seq}


@logs_router.get("/audit")
def list_audit_logs(
    since_seq: int | None = None,
    limit: int = 500,
    _: AuthContext = Depends(admin),
    svc: CoreServices = Depends(get_services),
):
    events = svc.audit.history(since_seq=since_seq, limit=min(limit, 2000))
    return {"events": [e.model_dump() for e in events]}


sensors_router = APIRouter(prefix="/api/v1/sensors", tags=["sensors"])


@sensors_router.get("")
def list_sensors(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    return {"sensors": svc.state.get_sensors()}


@sensors_router.get("/{sensor_type}")
def sensor_detail(sensor_type: str, _: AuthContext = Depends(viewer),
                  svc: CoreServices = Depends(get_services)):
    data = svc.state.get_sensor(sensor_type)
    if data is None:
        raise ApiError("NOT_FOUND", 404, f"sensor '{sensor_type}' has no data yet")
    return data


slam_router = APIRouter(prefix="/api/v1/slam", tags=["slam"])


class SlamSaveRequest(BaseModel):
    name: str = "rosy_map"


@slam_router.post("/start")
def slam_start(auth: AuthContext = Depends(operator), svc: CoreServices = Depends(get_services)):
    svc.capability.require("slam")
    svc.nav.start_mapping(source=f"api:{auth.role}")
    return {"mapping": True}


@slam_router.post("/stop")
def slam_stop(auth: AuthContext = Depends(operator), svc: CoreServices = Depends(get_services)):
    svc.capability.require("slam")
    svc.nav.stop_mapping(source=f"api:{auth.role}")
    return {"mapping": False}


@slam_router.post("/save")
def slam_save(body: SlamSaveRequest, auth: AuthContext = Depends(operator),
              svc: CoreServices = Depends(get_services)):
    svc.capability.require("slam")
    try:
        map_id = svc.nav.save_map(body.name, source=f"api:{auth.role}")
    except RuntimeError as exc:
        raise ApiError("CAPABILITY_NOT_SUPPORTED", 501, str(exc))
    return {"map_id": map_id}


@slam_router.post("/reset")
def slam_reset(auth: AuthContext = Depends(operator), svc: CoreServices = Depends(get_services)):
    svc.capability.require("slam")
    svc.nav.reset_mapping(source=f"api:{auth.role}")
    return {"reset": True}



docking_router = APIRouter(prefix="/api/v1/docking", tags=["docking"])

#: DockError 코드 → HTTP. 거부 사유를 그대로 계약으로 노출한다.
_DOCK_HTTP = {
    "NOT_FOUND": 404,
    "DOCK_EXISTS": 409,
    "UNKNOWN_DOCK_TYPE": 400,
    "MAP_MISMATCH": 409,
    "EMERGENCY_ACTIVE": 409,
    "DOCKING_ACTIVE": 409,
    "NOT_DOCKED": 409,
    "DOCK_REQUIRED": 400,
    "CAPABILITY_NOT_SUPPORTED": 501,
}


def _dock_error(exc: DockError) -> ApiError:
    return ApiError(exc.code, _DOCK_HTTP.get(exc.code, 400), str(exc))


class DockTypeRequest(BaseModel):
    name: str
    detector: str = "simulated"
    staging_offset_m: float = 0.7
    docking_threshold_m: float = 0.05
    max_retries: int = 3
    undock_distance_m: float = 0.35


class DockRequest(BaseModel):
    id: str
    type: str
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    map_id: str | None = None
    agent_url: str | None = None


class DockCommand(BaseModel):
    dock: str | None = None


@docking_router.get("/status")
def docking_status(_: AuthContext = Depends(viewer),
                   svc: CoreServices = Depends(get_services)):
    """상태 조회는 capability 로 막지 않는다 — 막으면 대시보드가 "도킹 없음"
    조차 표시할 수 없다."""
    body = svc.docking.status().model_dump()
    body["supported"] = svc.capability.supports("docking.supported")
    return body


@docking_router.get("/docks")
def list_docks(_: AuthContext = Depends(viewer),
               svc: CoreServices = Depends(get_services)):
    return {"docks": [d.model_dump() for d in svc.docking.database.list()]}


@docking_router.post("/types")
def create_dock_type(body: DockTypeRequest, _: AuthContext = Depends(admin),
                     svc: CoreServices = Depends(get_services)):
    try:
        return svc.docking.database.add_type(DockType(**body.model_dump())).model_dump()
    except (DockError, ValueError) as exc:
        raise _dock_error(exc) if isinstance(exc, DockError) else \
            ApiError("VALIDATION_ERROR", 400, str(exc))


@docking_router.post("/docks")
def create_dock(body: DockRequest, _: AuthContext = Depends(admin),
                svc: CoreServices = Depends(get_services)):
    try:
        return svc.docking.database.add(DockInstance(**body.model_dump())).model_dump()
    except DockError as exc:
        raise _dock_error(exc)


@docking_router.delete("/docks/{dock_id}")
def delete_dock(dock_id: str, _: AuthContext = Depends(admin),
                svc: CoreServices = Depends(get_services)):
    try:
        svc.docking.database.remove(dock_id)
    except DockError as exc:
        raise _dock_error(exc)
    return {"deleted": dock_id}


@docking_router.post("/docks/{dock_id}/teach")
def teach_dock(dock_id: str, auth: AuthContext = Depends(operator),
               svc: CoreServices = Depends(get_services)):
    """teach-by-docking — 지금 로봇이 선 자리를 도크 포즈로 기록한다.

    줄자로 SLAM 맵 좌표를 재서 쓸 만한 값이 나오지 않는다. 이렇게 기록해야
    포즈가 나중에 복귀에 쓸 바로 그 맵과 자기모순 없이 일치한다.
    """
    snapshot = svc.state.snapshot()
    try:
        taught = svc.docking.database.teach(
            dock_id, x=snapshot.pose.x, y=snapshot.pose.y, yaw=snapshot.pose.yaw,
            map_id=snapshot.map_id)
    except DockError as exc:
        raise _dock_error(exc)
    return taught.model_dump()


@docking_router.post("/dock")
def docking_dock(body: DockCommand, auth: AuthContext = Depends(operator),
                 svc: CoreServices = Depends(get_services)):
    svc.capability.require("docking.supported")       # DNC-003 — 미지원이면 501
    try:
        svc.docking.dock(body.dock)
    except DockError as exc:
        raise _dock_error(exc)
    return svc.docking.status().model_dump()


@docking_router.post("/undock")
def docking_undock(auth: AuthContext = Depends(operator),
                   svc: CoreServices = Depends(get_services)):
    svc.capability.require("docking.supported")
    try:
        svc.docking.undock()
    except DockError as exc:
        raise _dock_error(exc)
    return svc.docking.status().model_dump()


@docking_router.post("/cancel")
def docking_cancel(auth: AuthContext = Depends(operator),
                   svc: CoreServices = Depends(get_services)):
    svc.capability.require("docking.supported")
    svc.docking.cancel()
    return svc.docking.status().model_dump()


metrics_router = APIRouter(tags=["metrics"])

_HEALTH_VALUE = {"OK": 0, "UNKNOWN": 1, "WARNING": 2, "ERROR": 3}


@metrics_router.get("/metrics")
def metrics(svc: CoreServices = Depends(get_services)):
    import time as _time

    snap = svc.state.snapshot()
    lines = [
        "# HELP rosy_uptime_seconds rosy_core process uptime",
        "# TYPE rosy_uptime_seconds gauge",
        f"rosy_uptime_seconds {(_time.time() - svc.started_at):.1f}",
        "# HELP rosy_state_seq state snapshot sequence",
        "# TYPE rosy_state_seq counter",
        f"rosy_state_seq {snap.seq}",
        "# HELP rosy_events_published_total events published",
        "# TYPE rosy_events_published_total counter",
        f"rosy_events_published_total {svc.events.last_seq}",
        "# HELP rosy_battery_percent battery percent estimate",
        "# TYPE rosy_battery_percent gauge",
        f"rosy_battery_percent {snap.battery.percent if snap.battery.percent is not None else -1}",
        "# HELP rosy_diagnostics_health component health (0=OK,1=UNKNOWN,2=WARNING,3=ERROR)",
        "# TYPE rosy_diagnostics_health gauge",
    ]
    for component, health in snap.diagnostics_summary.items():
        lines.append(f'rosy_diagnostics_health{{component="{component}"}} {_HEALTH_VALUE[health.value]}')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


power_router = APIRouter(prefix="/api/v1/power", tags=["power"])


class PowerModeRequest(BaseModel):
    mode: PowerMode


@power_router.get("")
def power_status(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    """PWR-001: 현재 절전 모드·프레즌스·샘플링 주기."""
    return svc.power.status().model_dump()


@power_router.post("/wake")
def power_wake(auth: AuthContext = Depends(operator), svc: CoreServices = Depends(get_services)):
    """PWR-004: 원격 웨이크 — 로봇 앞에 서지 않고 정보 화면을 띄운다."""
    svc.power.wake("api")
    svc.state.set_power(svc.power.status())
    return svc.power.status().model_dump()


@power_router.post("/mode")
def power_set_mode(body: PowerModeRequest, auth: AuthContext = Depends(operator),
                   svc: CoreServices = Depends(get_services)):
    """운영자 강제 전환. 활동이 감지되면 정책이 다시 ACTIVE로 되돌린다."""
    svc.power.request_mode(body.mode, source=f"api:{auth.role}")
    svc.state.set_power(svc.power.status())
    return svc.power.status().model_dump()


# --- Network / Release / Commissioning (WP-5, 설계 §10.2/§10.3) --------------
#
# CORE 는 호스트 권한이 없으므로 이 세 화면의 데이터는 전부 Host Agent 에서 온다.
# 에이전트가 없는 상태(개발 장비, 서비스 미기동)는 예외가 아니라 정상적으로
# 있을 수 있는 상태이며, 그때 **없는 값을 그럴듯하게 채우지 않는다.** 빈 칸은
# 운영자에게 "이상 없음" 으로 읽히고, 지어낸 값은 사실로 읽힌다.

host_router = APIRouter(prefix="/api/v1/host", tags=["host"])


def _agent(svc: CoreServices) -> HostAgentClient:
    host_cfg = (svc.config or {}).get("host_agent", {})
    return HostAgentClient(
        socket_path=host_cfg.get("socket_path", "/run/rosy/host-agent.sock"),
        timeout_s=float(host_cfg.get("timeout_s", 5.0)),
    )


def _relay(reply, *, absent_detail: str) -> dict:
    """Turn an agent reply into a card payload that cannot mislead.

    ``available`` is the field the dashboard keys on. When it is false the
    card shows why instead of showing empty fields — an unreachable agent and
    a healthy device with nothing to report look identical otherwise.
    """
    if not reply.reachable:
        return {
            "available": False,
            "code": reply.code,
            "detail": reply.detail or absent_detail,
            "recovery": reply.recovery,
            "data": None,
        }
    return {
        "available": True,
        "ok": reply.ok,
        "code": reply.code,
        "detail": reply.detail,
        "recovery": reply.recovery,
        "data": reply.data,
    }


@host_router.get("/network")
def host_network(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    """현재 네트워크 모드와 도달성. SSID 는 표시하되 secret 은 절대 싣지 않는다."""
    reply = _agent(svc).request("network.status", role="viewer")
    return _relay(reply, absent_detail="Host Agent 에 연결할 수 없어 네트워크 상태를 알 수 없습니다.")


@host_router.get("/release")
def host_release(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    """current / previous / staged 와 마지막 실패 사유."""
    reply = _agent(svc).request("release.status", role="viewer")
    return _relay(reply, absent_detail="Host Agent 에 연결할 수 없어 릴리스 상태를 알 수 없습니다.")


class HostActionRequest(BaseModel):
    """파괴적 명령의 공통 입력.

    `confirmed` 는 대시보드의 재확인이 실제로 있었음을 뜻한다. 기본값이 False 인
    것이 핵심이다 — 빠뜨리면 실행되지 않고 거부된다.
    """

    confirmed: bool = False
    idempotency_key: str | None = None


class ReleaseInstallRequest(HostActionRequest):
    release_id: str = Field(min_length=1, max_length=64)


@host_router.post("/release/install")
def host_release_install(
    body: ReleaseInstallRequest,
    auth: AuthContext = Depends(admin),
    svc: CoreServices = Depends(get_services),
):
    reply = _agent(svc).request(
        "release.install",
        role="administrator",
        user_id=auth.token[:8],
        confirmed=body.confirmed,
        params={"release_id": body.release_id},
        idempotency_key=body.idempotency_key,
    )
    return _relay(reply, absent_detail="Host Agent 에 연결할 수 없어 설치를 시작하지 못했습니다.")


@host_router.post("/release/rollback")
def host_release_rollback(
    body: HostActionRequest,
    auth: AuthContext = Depends(admin),
    svc: CoreServices = Depends(get_services),
):
    reply = _agent(svc).request(
        "release.rollback",
        role="administrator",
        user_id=auth.token[:8],
        confirmed=body.confirmed,
        idempotency_key=body.idempotency_key,
    )
    return _relay(reply, absent_detail="Host Agent 에 연결할 수 없어 롤백을 시작하지 못했습니다.")


@host_router.post("/release/clear-hold")
def host_release_clear_hold(
    body: HostActionRequest,
    auth: AuthContext = Depends(admin),
    svc: CoreServices = Depends(get_services),
):
    """RECOVERY HOLD 해제. 홀드 중에는 install 이 거부되므로 별도의 의도적 행위다."""
    reply = _agent(svc).request(
        "release.clear_hold",
        role="administrator",
        user_id=auth.token[:8],
        confirmed=body.confirmed,
        idempotency_key=body.idempotency_key,
    )
    return _relay(reply, absent_detail="Host Agent 에 연결할 수 없어 홀드를 해제하지 못했습니다.")


@host_router.get("/commissioning")
def host_commissioning(_: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    """runtime mode 와 hardware 재승인 사유.

    runtime mode 는 CORE 가 스스로 안다 — 자기가 무엇으로 기동했는지는 호스트에
    묻지 않아도 된다. 그래서 이 카드는 에이전트가 없어도 절반은 정직하게 채운다.
    """
    mode = (svc.config or {}).get("runtime", {}).get("mode", "core")
    if mode == "core":
        detail = (
            "UART·모터 미승인 상태입니다. 이것은 정상이며, 승격은 별도 현장 안전 "
            "절차를 따릅니다."
        )
    elif mode == "motor":
        detail = (
            "모터 벤치 모드입니다. LiDAR는 아직 꺼져 있으며 hardware 모드는 "
            "별도 수락이 필요합니다. 배터리 ADC, IMU, SLAM, Fleet는 없습니다."
        )
    else:
        detail = (
            f"현재 {mode} 모드로 기동되어 있습니다. 모터와 LiDAR와 Nav2는 이 "
            "슬라이스에 있습니다. 배터리 전압(ADC), IMU, SLAM, Fleet는 "
            "띄우지 않습니다."
        )
    return {
        "runtime_mode": mode,
        "motor_hold": mode == "core",
        "lidar_hold": mode != "hardware",
        "battery_hold": True,
        "imu_hold": True,
        "slam_hold": True,
        "fleet_hold": True,
        "detail": detail,
    }
