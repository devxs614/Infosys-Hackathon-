"""A single deterministic ScenarioStream fanned out into independent worlds."""
from __future__ import annotations

from dataclasses import dataclass

from edge_server.models import Disruption, EventType, Order
from edge_server.simulation.order_generator import OrderGenerator


@dataclass(frozen=True, slots=True)
class ScenarioTick:
    orders: list[Order]
    events: list[Disruption]


class ScenarioStream:
    """Precomputes all random inputs so driver decisions cannot alter the scenario."""

    def __init__(self, seed: int, shift_minutes: int) -> None:
        self.seed = seed
        self.shift_minutes = shift_minutes
        self._orders = OrderGenerator(seed).schedule_shift(shift_minutes)
        self._events = [
            Disruption(id="E-HEAT", event_type=EventType.EXTREME_HEAT, zone="Monterrey", start_minute=35, description="40°C extreme heat"),
            Disruption(id="E-SURGE", event_type=EventType.SAN_PEDRO_SURGE, zone="San Pedro", start_minute=60, description="San Pedro high demand surge"),
            Disruption(id="E-RAIN", event_type=EventType.TORRENTIAL_RAIN, zone="Monterrey", start_minute=100, description="Torrential rain reduces visibility"),
            Disruption(id="E-FLOOD", event_type=EventType.GONZALITOS_FLOOD, zone="Gonzalitos", start_minute=120, description="Flooding severely reduces speed"),
            Disruption(id="E-CLOSURE", event_type=EventType.ROAD_CLOSURE, zone="Obispado", start_minute=170, description="Road closure near Obispado"),
        ]

    def tick(self, previous_minute: float, current_minute: float) -> ScenarioTick:
        orders = [item.order.model_copy(deep=True) for item in self._orders if previous_minute <= item.created_minute < current_minute]
        events = [event.model_copy(deep=True) for event in self._events if previous_minute <= event.start_minute < current_minute]
        return ScenarioTick(orders=orders, events=events)

