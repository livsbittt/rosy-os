"""rosy_core.api.app — FastAPI 팩토리 (P1-9, API-101). 계약: ROSY-API-REF-001."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from rosy_core.api.errors import ApiError, register_exception_handlers
from rosy_core.api.v1.routes import (
    control_router,
    events_router,
    logs_router,
    host_router,
    map_router,
    metrics_router,
    navigation_router,
    power_router,
    robot_router,
    safety_router,
    sensors_router,
    slam_router,
    swarm_router,
    system_router,
    waypoints_router,
    docking_router,
)
from rosy_core.api.ws import ws_router
from rosy_core.services import CoreServices


def create_app(config: dict[str, Any], services: CoreServices) -> FastAPI:
    app = FastAPI(
        title="ROSY CORE API",
        version="1.0.0",
        description="로봇 미들웨어 API — 계약: ROSY-API-REF-001 (v1.2)",
    )
    app.state.core = services
    register_exception_handlers(app)

    web_root = Path(__file__).resolve().parent.parent / "web"
    dashboard_assets = {
        "styles.css": "text/css",
        "app.js": "application/javascript",
        "map.js": "application/javascript",
        "dom.js": "application/javascript",
        "client.js": "application/javascript",
        "settings.js": "application/javascript",
    }

    app.include_router(system_router)
    app.include_router(robot_router)
    app.include_router(control_router)
    app.include_router(safety_router)
    app.include_router(navigation_router)
    app.include_router(map_router)
    app.include_router(waypoints_router)
    app.include_router(events_router)
    app.include_router(logs_router)
    app.include_router(power_router)
    app.include_router(sensors_router)
    app.include_router(slam_router)
    app.include_router(docking_router)
    app.include_router(swarm_router)
    app.include_router(metrics_router)
    app.include_router(host_router)
    app.include_router(ws_router)

    @app.get("/api/v1", tags=["system"])
    def root() -> dict:
        return {"name": "rosy_core", "api_versions": ["v1"]}

    @app.get("/", include_in_schema=False)
    def dashboard_redirect():
        return RedirectResponse("/dashboard")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard():
        return FileResponse(
            web_root / "index.html",
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache",
                "Content-Security-Policy": (
                    "default-src 'self'; connect-src 'self' ws: wss:; "
                    "img-src 'self' data:; style-src 'self'; script-src 'self'; "
                    "frame-ancestors 'none'; base-uri 'self'"
                ),
            },
        )

    @app.get("/dashboard/assets/{asset_name:path}", include_in_schema=False)
    def dashboard_asset(asset_name: str):
        media_type = dashboard_assets.get(asset_name)
        if media_type is None:
            raise HTTPException(status_code=404, detail="dashboard asset not found")
        return FileResponse(
            web_root / asset_name,
            media_type=media_type,
            headers={"Cache-Control": "no-cache"},
        )

    return app
