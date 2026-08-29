"""rosy_core.api.app — FastAPI 팩토리 (P1-9, API-101). 계약: ROSY-API-REF-001."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from rosy_core.api.errors import ApiError, register_exception_handlers
from rosy_core.api.v1.routes import (
    control_router,
    events_router,
    navigation_router,
    robot_router,
    safety_router,
    system_router,
    waypoints_router,
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

    app.include_router(system_router)
    app.include_router(robot_router)
    app.include_router(control_router)
    app.include_router(safety_router)
    app.include_router(navigation_router)
    app.include_router(waypoints_router)
    app.include_router(events_router)
    app.include_router(ws_router)

    @app.get("/api/v1", tags=["system"])
    def root() -> dict:
        return {"name": "rosy_core", "api_versions": ["v1"]}

    return app
