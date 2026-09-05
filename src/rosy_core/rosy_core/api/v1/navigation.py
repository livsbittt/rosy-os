"""rosy_core.api.v1.navigation — NAV-001~005 주행·SLAM, MAP-003 스냅샷, WPT-002 웨이포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from rosy_core.api.v1.common import enter_navigation_mode, operator, viewer
from rosy_core.api.deps import AuthContext, get_services
from rosy_core.api.errors import ApiError
from rosy_core.maps import valid_costmap_scope
from rosy_core.services import CoreServices
from rosy_core.waypoints.manager import Waypoint


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
    enter_navigation_mode(svc, auth)
    svc.nav.goal(spec, source=f"api:{auth.role}")
    return {
        "accepted": True,
        "mode": svc.modes.mode.value,
        "goal": {"x": spec.x, "y": spec.y, "yaw": spec.yaw},
    }


@navigation_router.post("/navigation/cancel")
def navigation_cancel(auth: AuthContext = Depends(operator),
                      svc: CoreServices = Depends(get_services)):
    svc.nav.cancel(source=f"api:{auth.role}")
    return {"navigation": svc.nav.nav_state.value}


@navigation_router.post("/navigation/home")
def navigation_home(auth: AuthContext = Depends(operator),
                    svc: CoreServices = Depends(get_services)):
    svc.capability.require("navigation.return_home")
    enter_navigation_mode(svc, auth)
    svc.nav.home(source=f"api:{auth.role}")
    return {"accepted": True, "mode": svc.modes.mode.value}


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
