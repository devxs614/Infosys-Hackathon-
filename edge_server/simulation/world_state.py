"""Mutable per-driver world, intentionally separated after ScenarioStream fan-out."""
from __future__ import annotations

from dataclasses import dataclass, field

from edge_server.models import Decision, DriverState, Order, OrderStatus, TrafficState, WeatherState, WorldState


@dataclass(slots=True)
class ActiveTrip:
    order_ids: list[str]
    remaining_minutes: float
    total_minutes: float
    distance_km: float
    final_lat: float
    final_lon: float
    decision: Decision


@dataclass(slots=True)
class DriverWorld:
    """A driver-specific copy of orders and state fed from one shared scenario."""
    driver: DriverState
    orders: dict[str, Order] = field(default_factory=dict)
    weather: WeatherState = field(default_factory=WeatherState)
    traffic: TrafficState = field(default_factory=TrafficState)
    events: list = field(default_factory=list)
    trip: ActiveTrip | None = None
    last_decision: Decision | None = None

    def add_orders(self, orders: list[Order]) -> None:
        self.orders.update({order.id: order.model_copy(deep=True) for order in orders})

    def available_orders(self, simulation_minute: float) -> list[Order]:
        for order in self.orders.values():
            if order.status == OrderStatus.AVAILABLE and order.delivery_deadline <= simulation_minute:
                order.status = OrderStatus.EXPIRED
        return [order for order in self.orders.values() if order.status == OrderStatus.AVAILABLE]

    def snapshot(self, simulation_minute: float, zones: dict[str, tuple[float, float]]) -> WorldState:
        return WorldState(simulation_minute=simulation_minute, weather=self.weather, traffic=self.traffic,
                          orders=list(self.orders.values()), drivers={self.driver.driver_id: self.driver},
                          events=self.events, zones=zones)
