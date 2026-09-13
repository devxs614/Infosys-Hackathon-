"""Central, WebSocket-broadcast simulation controls for every Rumbo laptop.

This is deliberately separate from the deterministic evaluation engine.  It
owns only the shared presentation shift clock and the interactive demo shocks;
the `/decide` fast path and its practice-pack contract remain untouched.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any


class SimulationControlState:
    """Small lock-protected source of truth for the live demo controls."""

    MINUTES_PER_REAL_SECOND = 0.25  # 15×: one real second represents 15 sim seconds.

    def __init__(self) -> None:
        self._state: dict[str, Any] = {
            "simulated_minutes": 14 * 60,
            "paused": False,
            "shock": None,
            "shock_zone": None,
            "road_closures": [],
            "driver_delays": {},
            "surge_multiplier": 1.0,
        }
        self._lock = asyncio.Lock()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return deepcopy(self._state)

    async def advance(self, real_seconds: float) -> dict[str, Any] | None:
        """Advance once on the Pi; `None` means no visible state changed."""
        async with self._lock:
            if self._state["paused"]:
                return None
            self._state["simulated_minutes"] += max(0.0, real_seconds) * self.MINUTES_PER_REAL_SECOND
            return deepcopy(self._state)

    async def update_time(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            if "simulated_minutes" in payload:
                self._state["simulated_minutes"] = max(0.0, min(1439.99, float(payload["simulated_minutes"])))
            if "paused" in payload:
                self._state["paused"] = bool(payload["paused"])
            return deepcopy(self._state)

    async def update_shock(self, shock: str | None, zone: str | None = None) -> dict[str, Any]:
        async with self._lock:
            self._state["shock"] = shock
            self._state["shock_zone"] = zone
            self._state["surge_multiplier"] = 1.45 if shock == "surge" else 1.0
            return deepcopy(self._state)

    async def add_road_closure(self, position: list[float], label: str | None = None) -> dict[str, Any]:
        async with self._lock:
            closure = {"position": [float(position[0]), float(position[1])], "label": label or "Pinned road closure"}
            self._state["road_closures"] = [*self._state["road_closures"], closure]
            self._state["shock"] = "closure"
            return deepcopy(self._state)

    async def delay_driver(self, driver_id: str, minutes: float) -> dict[str, Any]:
        async with self._lock:
            self._state["driver_delays"][driver_id] = {
                "minutes": max(1.0, float(minutes)),
                "until_minute": self._state["simulated_minutes"] + max(1.0, float(minutes)),
            }
            self._state["shock"] = "delay"
            return deepcopy(self._state)
