"""Optional asyncpg connection wrapper; no database is required for a demo."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TigerDB:
    def __init__(self, dsn: str = "", enabled: bool = True) -> None:
        self.dsn = dsn
        self.enabled = enabled and bool(dsn)
        self.pool: Any | None = None
        self.last_error: str | None = None

    async def connect(self) -> bool:
        if not self.enabled:
            return False
        try:
            import asyncpg
            self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=2, command_timeout=2)
            self.last_error = None
            logger.info("Tiger telemetry database connected")
            return True
        except Exception as exc:
            logger.warning("Tiger unavailable, using in-memory telemetry: %s", exc.__class__.__name__)
            self.pool = None
            self.last_error = exc.__class__.__name__
            return False

    async def insert_telemetry(self, values: dict[str, Any]) -> bool:
        if self.pool is None:
            return False
        query = """INSERT INTO telemetry (timestamp, simulation_time, driver_id, agent_type, decision, order_ids,
                   lat, lon, distance, duration, earnings, traffic, weather, temperature, surge, late_orders)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, values["timestamp"], values["simulation_time"], values["driver_id"],
                    values["agent_type"], values["decision"], values["order_ids"], values["lat"], values["lon"],
                    values["distance"], values["duration"], values["earnings"], values["traffic"], values["weather"],
                    values["temperature"], values["surge"], values["late_orders"])
            return True
        except Exception as exc:
            logger.warning("Tiger write failed, retaining memory telemetry: %s", exc.__class__.__name__)
            self.last_error = exc.__class__.__name__
            return False

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
