"""Simulation clock that compresses a full shift into a fixed demo duration."""
from __future__ import annotations


class SimulationClock:
    def __init__(self, shift_minutes: int = 240, demo_seconds: int = 180, tick_ms: int = 500) -> None:
        if shift_minutes <= 0 or demo_seconds <= 0 or tick_ms <= 0:
            raise ValueError("clock values must be positive")
        self.shift_minutes = shift_minutes
        self.demo_seconds = demo_seconds
        self.tick_ms = tick_ms
        self.current_minute = 0.0

    @property
    def minutes_per_tick(self) -> float:
        return self.shift_minutes * (self.tick_ms / 1000) / self.demo_seconds

    @property
    def finished(self) -> bool:
        return self.current_minute >= self.shift_minutes

    def tick(self) -> float:
        previous = self.current_minute
        self.current_minute = min(self.shift_minutes, self.current_minute + self.minutes_per_tick)
        return self.current_minute - previous

    def reset(self) -> None:
        self.current_minute = 0.0

