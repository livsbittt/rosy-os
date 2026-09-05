"""rosy_core.api.deps — SEC-101 인증·권한 (정적 토큰 3롤) + 서비스 접근."""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, Header, Query, Request

from rosy_core.api.errors import ApiError
from rosy_core.services import CoreServices

ROLE_RANK = {"viewer": 0, "operator": 1, "administrator": 2}


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def token_hint(token: str) -> str:
    value = str(token)
    if len(value) <= 6:
        return "••••"
    return f"{value[:3]}…{value[-2:]}"


def auth_entries(config: dict) -> list[dict]:
    entries = (config.get("auth") or {}).get("tokens", [])
    if isinstance(entries, dict):
        return [{"token": str(k), "role": str(v)} for k, v in entries.items() if k]
    return [
        {"token": str(item.get("token")), "role": str(item.get("role", "viewer"))}
        for item in entries
        if isinstance(item, dict) and item.get("token")
    ]


def public_token_records(config: dict) -> list[dict]:
    return [
        {
            "fingerprint": token_fingerprint(item["token"]),
            "role": item["role"] if item["role"] in ROLE_RANK else "viewer",
            "hint": token_hint(item["token"]),
        }
        for item in auth_entries(config)
    ]


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
    return {item["token"]: item["role"] for item in auth_entries(config)}


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
