"""Telemetry service that transparently mirrors values in memory."""
from __future__ import annotations

from edge_server.data.tiger_db import TigerDB
from edge_server.models import Telemetry


class TelemetryService:
    def __init__(self, database: TigerDB) -> None:
        self.database = database
        self.memory: list[Telemetry] = []

    async def start(self) -> None:
        await self.database.connect()

    async def record(self, event: Telemetry) -> None:
        self.memory.append(event)
        await self.database.insert_telemetry(event.model_dump())

    async def close(self) -> None:
        await self.database.close()

