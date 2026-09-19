"""Fleet 서버의 HTTP 표면 — 관제 UI 와 그 UI 가 쓰는 사이트 API.

경로는 로봇 계약(`/api/v1/...`)과 일부러 다르다. 관제 API 는 사이트 것이고, 로봇 것을
흉내 내면 둘 중 어느 쪽에 말하고 있는지 화면에서도 코드에서도 흐려진다.

인증: 이 서버는 robots.yaml 의 운영자 토큰을 들고 있다. 즉 이 포트에 닿는 사람은 현장의
모든 로봇을 움직일 수 있다. 그래서 기본은 루프백이고, 루프백 밖으로 열려면 콘솔 토큰을
반드시 받는다(`serve()` 가 강제한다).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from fleet.hub.hub import HubError
from fleet.server.console import FleetConsole
from fleet.swarm.transport import RobotApiError

WEB_ROOT = Path(__file__).resolve().parent / "web"

#: 경로 순회를 막는 유일한 방어다 — 디렉터리 스캔으로 바꾸지 않는다 (core 와 같은 규칙).
CONSOLE_ASSETS = {
    "tokens.css": "text/css",
    "styles.css": "text/css",
    "console.js": "application/javascript",
}

CONSOLE_CSP = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


class GoalRequest(BaseModel):
    x: float
    y: float
    yaw: float = 0.0


class FormationRequest(BaseModel):
    leader: str
    formation: str = "COLUMN"
    spacing: Optional[float] = None
    max_speed: Optional[float] = None


class ReformRequest(BaseModel):
    formation: str
    spacing: Optional[float] = None


def _http_error(exc: BaseException) -> HTTPException:
    if isinstance(exc, HubError):
        # 409 는 "지금 상태에서는 안 된다"(이미 대형이 열려 있음, 팔로워가 대형에 묶임)이고,
        # 400 은 "요청이 틀렸다"(없는 대형 이름)다. 화면이 둘을 다르게 안내해야 한다.
        conflict = {"FORMATION_ACTIVE", "NO_FORMATION", "REFORM_REFUSED",
                    "RESUME_REFUSED", "ARMING_FAILED", "NO_FOLLOWERS"}
        status = 404 if exc.code == "UNKNOWN_ROBOT" else 409 if exc.code in conflict else 400
        return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, RobotApiError):
        # 로봇이 거절한 것이지 관제가 잘못 만든 요청이 아니다 — 502 로 그 사실을 남긴다.
        return HTTPException(status_code=502,
                             detail={"code": exc.code, "message": str(exc),
                                     "robot_id": exc.robot_id})
    return HTTPException(status_code=502,
                         detail={"code": type(exc).__name__, "message": str(exc)})


def create_app(console: FleetConsole, *, console_token: Optional[str] = None) -> FastAPI:
    app = FastAPI(
        title="ROSY Fleet",
        version="0.1.0",
        description="사이트 오케스트레이터 — 모음과 원자 액션 흩뿌림 (D-59)",
    )
    app.state.console = console

    def authorize(authorization: Optional[str] = Header(default=None)) -> None:
        if console_token is None:
            return
        if authorization != f"Bearer {console_token}":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED",
                                                         "message": "console token required"})

    guard = [Depends(authorize)]

    @app.get("/api/fleet/state", dependencies=guard, tags=["fleet"])
    async def fleet_state() -> dict:
        return await console.snapshot()

    @app.get("/api/fleet/map", dependencies=guard, tags=["fleet"])
    async def fleet_map() -> dict:
        grid = await console.map()
        if grid is None:
            raise HTTPException(status_code=404, detail={"code": "NO_MAP",
                                                         "message": "no robot served a map"})
        return grid

    @app.post("/api/fleet/robots/{robot_id}/goal", dependencies=guard, tags=["fleet"])
    async def fleet_goal(robot_id: str, body: GoalRequest) -> dict:
        try:
            return await console.goal(robot_id, body.x, body.y, body.yaw)
        except (HubError, RobotApiError, OSError) as exc:
            raise _http_error(exc) from exc

    @app.post("/api/fleet/robots/{robot_id}/cancel", dependencies=guard, tags=["fleet"])
    async def fleet_cancel(robot_id: str) -> dict:
        try:
            return await console.cancel(robot_id)
        except (HubError, RobotApiError, OSError) as exc:
            raise _http_error(exc) from exc

    @app.get("/api/fleet/formation", dependencies=guard, tags=["formation"])
    async def formation_state() -> dict:
        return console.formation_status()

    @app.post("/api/fleet/formation/start", dependencies=guard, tags=["formation"])
    async def formation_start(body: FormationRequest) -> dict:
        try:
            return await console.formation_start(body.leader, body.formation,
                                                 body.spacing, body.max_speed)
        except (HubError, RobotApiError, OSError) as exc:
            raise _http_error(exc) from exc

    @app.post("/api/fleet/formation/reform", dependencies=guard, tags=["formation"])
    async def formation_reform(body: ReformRequest) -> dict:
        try:
            return await console.formation_reform(body.formation, body.spacing)
        except (HubError, RobotApiError, OSError) as exc:
            raise _http_error(exc) from exc

    @app.post("/api/fleet/formation/resume", dependencies=guard, tags=["formation"])
    async def formation_resume() -> dict:
        try:
            return await console.formation_resume()
        except (HubError, RobotApiError, OSError) as exc:
            raise _http_error(exc) from exc

    @app.post("/api/fleet/formation/stop", dependencies=guard, tags=["formation"])
    async def formation_stop() -> dict:
        # 해제는 거절하지 않는다. 대형을 못 푸는 화면은 대형을 여는 화면보다 나쁘다.
        return await console.formation_stop()

    @app.post("/api/fleet/estop", dependencies=guard, tags=["fleet"])
    async def fleet_estop() -> dict:
        # 이쪽은 한 대가 거절해도 200 이다 — 어느 대가 섰고 어느 대가 못 섰는지는 본문에
        # 다 들어 있고, 화면은 그 목록을 보여 줘야 한다.
        return await console.estop_all()

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/console")

    @app.get("/console", include_in_schema=False)
    def console_page():
        return FileResponse(
            WEB_ROOT / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache", "Content-Security-Policy": CONSOLE_CSP},
        )

    @app.get("/console/assets/{asset_name:path}", include_in_schema=False)
    def console_asset(asset_name: str):
        media_type = CONSOLE_ASSETS.get(asset_name)
        if media_type is None:
            raise HTTPException(status_code=404, detail="console asset not found")
        return FileResponse(WEB_ROOT / asset_name, media_type=media_type,
                            headers={"Cache-Control": "no-cache"})

    return app
