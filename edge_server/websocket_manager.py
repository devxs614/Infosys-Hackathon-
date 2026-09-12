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
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

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
            logger.debug("Removed %d stale WebSocket clients", len(failed))
