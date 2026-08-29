"""rosy_core.api.deps — SEC-101 인증·권한 (정적 토큰 3롤) + 서비스 접근."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Query, Request

from rosy_core.api.errors import ApiError
from rosy_core.services import CoreServices

ROLE_RANK = {"viewer": 0, "operator": 1, "administrator": 2}


class AuthContext:
    def __init__(self, token: str, role: str) -> None:
        self.token = token
        self.role = role

    @property
    def rank(self) -> int:
        return ROLE_RANK.get(self.role, -1)


def get_services(request: Request) -> CoreServices:
    return request.app.state.core


def _token_table(config: dict) -> dict[str, str]:
    entries = config.get("auth", {}).get("tokens", [])
    if isinstance(entries, dict):
        return {str(k): str(v) for k, v in entries.items()}
    return {str(e.get("token")): str(e.get("role", "viewer")) for e in entries if e.get("token")}


def authenticate(config: dict, bearer: Optional[str], query_token: Optional[str]) -> AuthContext:
    token = bearer.removeprefix("Bearer ").strip() if bearer else (query_token or "").strip()
    table = _token_table(config)
    if not token or token not in table:
        raise ApiError("UNAUTHORIZED", 401, "missing or invalid token")
    return AuthContext(token=token, role=table[token])


def auth_dependency(request: Request,
                    authorization: Optional[str] = Header(default=None)) -> AuthContext:
    return authenticate(request.app.state.core.config, authorization, None)


def require_role(min_role: str):
    def _dep(auth: AuthContext = Depends(auth_dependency)) -> AuthContext:
        if auth.rank < ROLE_RANK[min_role]:
            raise ApiError("FORBIDDEN", 403, f"requires {min_role} role")
        return auth
    return _dep
