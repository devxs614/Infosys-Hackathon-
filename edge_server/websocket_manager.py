"""Local WebSocket connection registry; simulator never depends on clients."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._users: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def bind_user(self, websocket: WebSocket, user_id: str) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._users[websocket] = user_id

    async def user_id_for(self, websocket: WebSocket) -> str | None:
        async with self._lock:
            return self._users.get(websocket)

    async def has_user_connection(self, user_id: str) -> bool:
        async with self._lock:
            return user_id in self._users.values()

    async def disconnect(self, websocket: WebSocket) -> tuple[str | None, bool]:
        async with self._lock:
            self._connections.discard(websocket)
            user_id = self._users.pop(websocket, None)
            still_connected = bool(user_id and user_id in self._users.values())
        return user_id, still_connected

    @property
    def count(self) -> int:
        return len(self._connections)

    async def send(self, websocket: WebSocket, message_type: str, data: dict[str, Any]) -> None:
        await websocket.send_json({"type": message_type, "timestamp": int(time.time() * 1000), "data": data})

    async def broadcast(self, message_type: str, data: dict[str, Any]) -> None:
        payload = {"type": message_type, "timestamp": int(time.time() * 1000), "data": data}
        async with self._lock:
            peers = list(self._connections)
        failed: list[WebSocket] = []
        for peer in peers:
            try:
                await peer.send_json(payload)
            except Exception:  # A stale socket must not stop the demo.
                failed.append(peer)
        if failed:
            async with self._lock:
                for peer in failed:
                    self._connections.discard(peer)
                    self._users.pop(peer, None)
            logger.debug("Removed %d stale WebSocket clients", len(failed))

    async def send_to_user(self, user_id: str, message_type: str, data: dict[str, Any]) -> bool:
        payload = {"type": message_type, "timestamp": int(time.time() * 1000), "data": data}
        async with self._lock:
            peers = [socket for socket, current_user_id in self._users.items() if current_user_id == user_id]
        delivered = False
        failed: list[WebSocket] = []
        for peer in peers:
            try:
                await peer.send_json(payload)
                delivered = True
            except Exception:
                failed.append(peer)
        if failed:
            async with self._lock:
                for peer in failed:
                    self._connections.discard(peer)
                    self._users.pop(peer, None)
        return delivered
