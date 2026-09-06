"""rosy_core.api.v1.map — MAP-003 점유맵·코스트맵 스냅샷 조회."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rosy_core.api.v1.common import viewer
from rosy_core.api.deps import AuthContext, get_services
from rosy_core.api.errors import ApiError
from rosy_core.maps import valid_costmap_scope
from rosy_core.services import CoreServices


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
