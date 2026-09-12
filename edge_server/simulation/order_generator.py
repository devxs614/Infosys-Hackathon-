"""Seeded Monterrey-inspired order factory."""
from __future__ import annotations

import random
from dataclasses import dataclass

from edge_server.models import Order
from edge_server.routing.fallback_router import haversine_km

ZONES: dict[str, tuple[float, float]] = {
    "Tec": (25.6517, -100.2892), "San Agustín": (25.6528, -100.3376),
    "Obispado": (25.6810, -100.3477), "Centrito Valle": (25.6510, -100.3760),
    "Macroplaza": (25.6668, -100.3090), "San Jerónimo": (25.6971, -100.3605),
    "San Pedro": (25.6605, -100.4030), "Gonzalitos": (25.6903, -100.3558),
}
RESTAURANTS = ("Tacos Norteños", "Café Sierra", "La Pasta", "Bowl MX", "Mercado Local", "Tortas Regias")


@dataclass(frozen=True, slots=True)
class ScheduledOrder:
    created_minute: float
    order: Order


class OrderGenerator:
    """Produces the exact same scheduled stream for the same seed."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self._counter = 0

    def make_order(self, simulation_minute: float, surge_multiplier: float = 1.0) -> Order:
        self._counter += 1
        pickup_zone = self.random.choice(tuple(ZONES))
        dropoff_zone = self.random.choice(tuple(ZONES))
        while dropoff_zone == pickup_zone:
            dropoff_zone = self.random.choice(tuple(ZONES))
        pickup = ZONES[pickup_zone]
        dropoff = ZONES[dropoff_zone]
        distance = max(.8, haversine_km(*pickup, *dropoff) * 1.22)
        base_payout = round(30 + distance * self.random.uniform(7, 11), 2)
        minutes = round(7 + distance * self.random.uniform(2.5, 3.8), 2)
        return Order(
            id=f"O{self._counter:03d}", restaurant=self.random.choice(RESTAURANTS), pickup_lat=pickup[0], pickup_lon=pickup[1],
            dropoff_lat=dropoff[0], dropoff_lon=dropoff[1], payout_mxn=base_payout * 1.35,
            courier_payout_mxn=base_payout, distance_km=round(distance, 2), estimated_minutes=minutes,
            pickup_deadline=round(simulation_minute + self.random.uniform(10, 24), 2),
            delivery_deadline=round(simulation_minute + minutes + self.random.uniform(20, 38), 2),
            priority=self.random.randint(1, 5), customer_rating=round(self.random.uniform(4.1, 5), 1),
            surge_multiplier=surge_multiplier, zone=pickup_zone,
        )

    def schedule_shift(self, shift_minutes: int) -> list[ScheduledOrder]:
        entries: list[ScheduledOrder] = []
        for minute in range(0, shift_minutes, 7):
            amount = 1 + (1 if self.random.random() < .32 else 0)
            for _ in range(amount):
                surge = self.random.uniform(1.0, 1.25)
                entries.append(ScheduledOrder(float(minute), self.make_order(float(minute), surge)))
        return entries

