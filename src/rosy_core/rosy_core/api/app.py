"""rosy_core.api.app — FastAPI 팩토리 (P1-9 스캘폴딩, API-101).

라우터는 v1/ 모듈에서 단계적으로 추가 (system → robot → navigation → ...).
OpenAPI는 ROSY-API-REF-001과 계약 테스트로 동기화된다 (API-004).
"""

from __future__ import annotations

from typing import Any


def create_app(config: dict[str, Any]):
    from fastapi import FastAPI

    app = FastAPI(
        title="ROSY CORE API",
        version="1.0.0",
        description="로봇 미들웨어 API — 계약: ROSY-API-REF-001",
    )

    @app.get("/api/v1/system/info", tags=["system"])
    def system_info() -> dict:
        """IDN-003 Robot Information (P1-2)."""
        return {
            "robot_id": config.get("robot", {}).get("id", "rosy_01"),
            "robot_name": config.get("robot", {}).get("name", "Rosy 01"),
            "software_version": "0.1.0",
            "api_versions": ["v1"],
        }

    return app
