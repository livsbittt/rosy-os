"""rosy_core.api.v1 라우터 — API Ref §5 계약 구현 (P1-9)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rosy_core.api.deps import AuthContext, auth_dependency, get_services, require_role
from rosy_core.api.errors import ApiError
from rosy_core.command.arbitration import Mode
from rosy_core.protocol.schemas import PowerMode, RobotMode
from rosy_core.services import CoreServices
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
    manual_linear: Optional[float] = None
    manual_angular: Optional[float] = None


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
    x: Optional[float] = None
    y: Optional[float] = None
    yaw: Optional[float] = 0.0
    waypoint: Optional[str] = None


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


@events_router.get("")
def list_events(since_seq: Optional[int] = None, limit: int = 100,
                _: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    events = svc.events.history(since_seq=since_seq, limit=limit)
    return {"events": [e.model_dump() for e in events], "last_seq": svc.events.last_seq}


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
