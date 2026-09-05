"""rosy_core.api.v1.swarm — SWM-002 follow 프리미티브 (API Ref §5.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from rosy_core.api.v1.common import enter_navigation_mode, operator, viewer
from rosy_core.api.deps import AuthContext, get_services
from rosy_core.api.errors import ApiError
from rosy_core.navigation.swarm import SwarmError
from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_core.services import CoreServices

swarm_router = APIRouter(prefix="/api/v1/swarm", tags=["swarm"])

#: SwarmError 코드 → HTTP. 도킹과 같은 규칙: 미지원은 501, 상태 충돌은 409.
_SWARM_HTTP = {
    "CAPABILITY_NOT_SUPPORTED": 501,
    "EMERGENCY_ACTIVE": 409,
    "VALIDATION_ERROR": 400,
}


def _swarm_error(exc: SwarmError) -> ApiError:
    return ApiError(exc.code, _SWARM_HTTP.get(exc.code, 400), str(exc))


@swarm_router.post("/follow")
def swarm_follow(body: SwarmFollowParams, auth: AuthContext = Depends(operator),
                 svc: CoreServices = Depends(get_services)):
    """추종 시작. 목표는 NAVIGATION 모드에서만 바퀴에 닿는다 (D-2, SWM-001)."""
    try:
        status = svc.swarm.follow(body, source=f"api:{auth.role}")
    except SwarmError as exc:
        raise _swarm_error(exc)
    # 모드 전이는 follow 가 성공한 뒤에만 한다. 거부된 명령이 모드를 바꾸면
    # 로봇은 아무 목표도 없이 NAVIGATION 에 앉아 있게 된다.
    enter_navigation_mode(svc, auth)
    return {**svc.swarm.state_payload(), "role": status.role.value}


@swarm_router.post("/cancel")
def swarm_cancel(auth: AuthContext = Depends(operator),
                 svc: CoreServices = Depends(get_services)):
    svc.swarm.cancel(source=f"api:{auth.role}")
    return svc.swarm.state_payload()


@swarm_router.get("/state")
def swarm_state(_: AuthContext = Depends(viewer),
                svc: CoreServices = Depends(get_services)):
    return svc.swarm.state_payload()
