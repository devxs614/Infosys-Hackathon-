"""WebSocket endpoint for local dashboard updates."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def simulation_websocket(websocket: WebSocket) -> None:
    manager = websocket.app.state.connections
    await manager.connect(websocket)
    try:
        await manager.send(websocket, "connection", {"status": "connected", "transport": "websocket"})
        await manager.send(websocket, "hello_response", {"service": "Courier Edge Decision System", "state": websocket.app.state.engine.state().model_dump(mode="json")})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await manager.send(websocket, "pong", {})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
