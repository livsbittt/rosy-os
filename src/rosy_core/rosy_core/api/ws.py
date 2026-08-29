"""rosy_core.api.ws — API-102 WebSocket 스트림 (/ws/state 10 Hz, /ws/events)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rosy_core.api.deps import authenticate

ws_router = APIRouter()


def _match_type(type_: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    for pattern in patterns:
        if pattern.endswith("*") and type_.startswith(pattern[:-1]):
            return True
        if type_ == pattern:
            return True
    return False


@ws_router.websocket("/ws/state")
async def ws_state(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    svc = websocket.app.state.core
    try:
        authenticate(svc.config, None, token)
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    rate = float(svc.config.get("state", {}).get("rate_hz", 10.0))
    try:
        while True:
            await websocket.send_json(svc.state.snapshot().model_dump())
            await asyncio.sleep(1.0 / rate)
    except WebSocketDisconnect:
        return
    except Exception:
        return


@ws_router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    svc = websocket.app.state.core
    try:
        authenticate(svc.config, None, token)
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    patterns = [p.strip() for p in websocket.query_params.get("types", "").split(",") if p.strip()]

    queue: asyncio.Queue = asyncio.Queue()

    def _on_event(event) -> None:
        try:
            queue.put_nowait(event)
        except Exception:
            pass

    unsubscribe = svc.events.subscribe(_on_event)
    try:
        while True:
            event = await queue.get()
            if _match_type(event.type, patterns):
                await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        unsubscribe()
