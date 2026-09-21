import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core_common.protocol.schemas import Envelope, EnvelopeType
from fleet.hub.hub import SiteHub

logger = logging.getLogger("hub.server")

def create_hub_app(hub: SiteHub) -> FastAPI:
    app = FastAPI(title="Rosy Site Hub")
    app.state.hub = hub

    @app.get("/registry")
    async def get_registry():
        return {
            rid: {
                "online": row.online,
                "snapshot": row.snapshot.model_dump(mode="json") if row.snapshot else None,
                "events": [e.model_dump(mode="json") for e in row.events]
            }
            for rid, row in hub.registry._robots.items()
        }

    @app.websocket("/ws/robots")
    async def ws_robots(websocket: WebSocket):
        await websocket.accept()
        robot_id: Optional[str] = None
        try:
            while True:
                text = await websocket.receive_text()
                try:
                    payload = json.loads(text)
                    env = Envelope.model_validate(payload)
                except Exception as exc:
                    logger.warning("invalid envelope %s", exc)
                    await websocket.close(code=1008)
                    break
                
                reply = hub.handle(env)
                if reply.type is EnvelopeType.ERROR:
                    code = reply.payload.get("code")
                    logger.warning("hub rejected %s: %s", env.type.value, code)
                    await websocket.send_json(reply.model_dump(exclude_none=True))
                    if env.type is EnvelopeType.HELLO:
                        await websocket.close(code=4401)
                        break
                    continue
                
                if reply.type is EnvelopeType.WELCOME:
                    robot_id = reply.payload.get("robot_id")
                    
                await websocket.send_json(reply.model_dump(exclude_none=True))
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.error("ws error: %s", exc)
        finally:
            if robot_id:
                row = hub.registry.record(robot_id)
                row.online = False

    return app
