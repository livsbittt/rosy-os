"""rosy_core.api.v1.control — 모드 전이와 SAF-002 teleop."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rosy_core.api.v1.common import operator
from rosy_core.api.deps import AuthContext, get_services
from rosy_core.api.errors import ApiError
from rosy_core.command.arbitration import Mode
from rosy_core.protocol.schemas import RobotMode
from rosy_core.services import CoreServices


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
