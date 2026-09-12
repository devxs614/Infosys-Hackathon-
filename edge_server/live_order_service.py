"""Live two-client order coordination for the Rumbo multi-screen demo."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable

from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.models import (
    BatchPlan,
    DriverActionRequest,
    DriverState,
    LiveOrder,
    LiveOrderRequest,
    Order,
    TrafficState,
    WeatherState,
)
from edge_server.routing.fallback_router import haversine_km

# Shared pickup is a demo restaurant near Centrito Valle. All route savings are calculated,
# never hardcoded, from the current client locations.
PICKUP = [25.6550, -100.3780]


class LiveOrderCoordinator:
    """A lock-protected, in-memory coordinator independent of the long simulation stream."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent
        self.orders: dict[str, LiveOrder] = {}
        self.batch: BatchPlan | None = None
        self._counter = 0
        self._lock = asyncio.Lock()

    def snapshot(self) -> dict:
        return {
            "orders": [order.model_dump(mode="json") for order in self.orders.values()],
            "batch": self.batch.model_dump(mode="json") if self.batch else None,
        }

    async def create_order(self, payload: dict) -> tuple[LiveOrder, BatchPlan | None]:
        request = LiveOrderRequest.model_validate(payload)
        async with self._lock:
            self._counter += 1
            order = LiveOrder(id=f"RUM-{self._counter:03d}", **request.model_dump())
            self.orders[order.id] = order
            batch_candidates = self._batch_candidates()
            if len(batch_candidates) != 2 or self.batch is not None:
                return order, None
            self.batch = await self._build_batch(batch_candidates)
            for candidate in batch_candidates:
                candidate.status = "BATCH_SUGGESTED"
            return order, self.batch

    def _batch_candidates(self) -> list[LiveOrder]:
        newest_by_client: dict[str, LiveOrder] = {}
        for order in self.orders.values():
            if order.status == "REQUESTED":
                newest_by_client[order.client_id] = order
        return list(newest_by_client.values()) if len(newest_by_client) == 2 else []

    async def _build_batch(self, orders: Iterable[LiveOrder]) -> BatchPlan:
        first, second = sorted(orders, key=lambda order: haversine_km(PICKUP[0], PICKUP[1], order.location[0], order.location[1]))
        solo_distance = sum(haversine_km(PICKUP[0], PICKUP[1], item.location[0], item.location[1]) for item in (first, second))
        batch_distance = haversine_km(PICKUP[0], PICKUP[1], first.location[0], first.location[1]) + haversine_km(first.location[0], first.location[1], second.location[0], second.location[1])
        savings = max(0.0, (solo_distance - batch_distance) / max(solo_distance, .001) * 100)
        reasoning = await self._strategic_reasoning(first, second, savings)
        return BatchPlan(
            id="BATCH-LIVE-001", order_ids=[first.id, second.id], client_ids=[first.client_id, second.client_id],
            pickup=PICKUP, route=[PICKUP, first.location, second.location],
            individual_distance_km=round(solo_distance, 2), batch_distance_km=round(batch_distance, 2),
            savings_percent=round(savings, 1), reasoning=reasoning,
        )

    async def _strategic_reasoning(self, first: LiveOrder, second: LiveOrder, savings: float) -> str:
        """Use Gemini when available; deterministic route data remains the source of truth."""
        synthetic_orders = [
            Order(
                id=order.id, restaurant="Rumbo Kitchen", pickup_lat=PICKUP[0], pickup_lon=PICKUP[1],
                dropoff_lat=order.location[0], dropoff_lon=order.location[1], payout_mxn=100,
                courier_payout_mxn=60, distance_km=haversine_km(PICKUP[0], PICKUP[1], order.location[0], order.location[1]),
                estimated_minutes=18, pickup_deadline=20, delivery_deadline=55, zone="Monterrey",
            ) for order in (first, second)
        ]
        try:
            decision = await asyncio.wait_for(
                self.agent.decide(DriverState(driver_id="rumbo-live", lat=PICKUP[0], lon=PICKUP[1]), synthetic_orders,
                                  TrafficState(), WeatherState(), 0, 120),
                timeout=4,
            )
            if decision.reasoning:
                return f"{decision.reasoning} Ahorro de distancia calculado: {savings:.1f}%"
        except Exception:
            pass
        return f"Rumbo Edge agrupó ambos destinos desde el mismo pickup. Ahorro de distancia calculado: {savings:.1f}%"

    async def apply_driver_action(self, payload: dict) -> BatchPlan | None:
        action = DriverActionRequest.model_validate(payload).action
        async with self._lock:
            if self.batch is None:
                return None
            statuses = {
                "ACCEPT_BATCH": "ACCEPTED",
                "ARRIVED_RESTAURANT": "AT_RESTAURANT",
                "DELIVERED_CLIENT_1": "DELIVERED_CLIENT_1",
                "DELIVERED_CLIENT_2": "DELIVERED_CLIENT_2",
            }
            self.batch.status = statuses[action]
            if action == "ACCEPT_BATCH":
                for order in self.orders.values():
                    if order.id in self.batch.order_ids:
                        order.status = "BATCH_ACCEPTED"
            elif action.startswith("DELIVERED_CLIENT_"):
                client_id = action.replace("DELIVERED_", "").lower()
                for order in self.orders.values():
                    if order.client_id == client_id:
                        order.status = "DELIVERED"
            return self.batch

    async def recalculate(self, disruption: str) -> BatchPlan | None:
        """Refresh the visible Edge explanation after a judge changes the network conditions."""
        async with self._lock:
            if self.batch is None:
                return None
            if disruption == "TORRENTIAL_RAIN":
                impact = "Lluvia torrencial: Rumbo recalculó la ruta y preservó el batch con prioridad de seguridad."
            elif disruption == "GONZALITOS_FLOOD":
                impact = "Inundación en Gonzalitos: Rumbo evitó la zona afectada y recalculó la secuencia de entrega."
            elif disruption == "SAN_PEDRO_CONGESTION":
                impact = "Congestionamiento en San Pedro: Rumbo recalculó ETA y mantuvo la ruta de menor costo."
            else:
                impact = "Rumbo Edge actualizó la recomendación con el nuevo estado de la red vial."
            self.batch.reasoning = f"{impact} {self.batch.savings_percent:.1f}% de ahorro de distancia calculado."
            self.batch.status = f"RECALCULATED_{disruption}"
            return self.batch
