"""Common decision-agent interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from edge_server.models import Decision, DriverState, Order, TrafficState, WeatherState


class BaseAgent(ABC):
    agent_name: str

    @abstractmethod
    async def decide(
        self, driver: DriverState, orders: list[Order], traffic: TrafficState, weather: WeatherState,
        simulation_minute: float, time_remaining: float,
    ) -> Decision:
        """Return one strategic proposal; the validator owns enforcement."""

