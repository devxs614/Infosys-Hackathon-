"""Shared API and simulation contracts. Values are intentionally JSON-friendly."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ACCEPTED = "ACCEPTED"
    PICKED_UP = "PICKED_UP"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class DecisionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    BATCH = "BATCH"
    WAIT = "WAIT"
    REPOSITION = "REPOSITION"


class EventType(str, Enum):
    EXTREME_HEAT = "EXTREME_HEAT"
    TORRENTIAL_RAIN = "TORRENTIAL_RAIN"
    GONZALITOS_FLOOD = "GONZALITOS_FLOOD"
    SAN_PEDRO_SURGE = "SAN_PEDRO_SURGE"
    ROAD_CLOSURE = "ROAD_CLOSURE"


class Order(BaseModel):
    id: str
    restaurant: str
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    payout_mxn: float = Field(ge=0)
    courier_payout_mxn: float = Field(ge=0)
    distance_km: float = Field(ge=0)
    estimated_minutes: float = Field(gt=0)
    created_at: datetime = Field(default_factory=utc_now)
    pickup_deadline: float = Field(ge=0, description="Simulated minute")
    delivery_deadline: float = Field(ge=0, description="Simulated minute")
    priority: int = Field(default=1, ge=1, le=5)
    customer_rating: float = Field(default=4.5, ge=1, le=5)
    surge_multiplier: float = Field(default=1.0, ge=1)
    status: OrderStatus = OrderStatus.AVAILABLE
    zone: str = "Monterrey"


class DriverState(BaseModel):
    driver_id: str
    lat: float
    lon: float
    available: bool = True
    current_order_ids: list[str] = Field(default_factory=list)
    shift_start: datetime = Field(default_factory=utc_now)
    shift_minutes_elapsed: float = Field(default=0, ge=0)
    earnings_mxn: float = Field(default=0, ge=0)
    distance_km: float = Field(default=0, ge=0)
    completed_orders: int = Field(default=0, ge=0)
    late_orders: int = Field(default=0, ge=0)
    accepted_orders: int = Field(default=0, ge=0)
    rejected_orders: int = Field(default=0, ge=0)
    batches: int = Field(default=0, ge=0)


class TrafficState(BaseModel):
    global_factor: float = Field(default=1.0, ge=0.2, le=5)
    affected_zones: list[str] = Field(default_factory=list)
    road_closures: list[str] = Field(default_factory=list)
    flooded_roads: list[str] = Field(default_factory=list)
    congestion_level: str = "normal"


class WeatherState(BaseModel):
    temperature_c: float = 28.0
    rain_intensity: float = Field(default=0, ge=0, le=1)
    visibility: float = Field(default=1, ge=0, le=1)
    flooding_risk: float = Field(default=0, ge=0, le=1)


class Disruption(BaseModel):
    id: str
    event_type: EventType
    zone: str
    start_minute: float
    active: bool = True
    description: str


class RouteEstimate(BaseModel):
    distance_km: float = Field(ge=0)
    duration_minutes: float = Field(ge=0)
    geometry: list[list[float]] = Field(default_factory=list)
    feasible: bool = True
    warnings: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    decision_type: DecisionType
    selected_order_ids: list[str] = Field(default_factory=list)
    reasoning: str = Field(min_length=1, max_length=1000)
    estimated_profit_mxn: float = Field(ge=0)
    estimated_distance_km: float = Field(ge=0)
    estimated_duration_minutes: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    timestamp: datetime = Field(default_factory=utc_now)
    reposition_lat: float | None = None
    reposition_lon: float | None = None

    @field_validator("selected_order_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("selected_order_ids must be unique")
        return value


class Telemetry(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    simulation_time: float
    driver_id: str
    agent_type: str
    decision: str
    order_ids: list[str] = Field(default_factory=list)
    lat: float
    lon: float
    distance: float
    duration: float
    earnings: float
    traffic: float
    weather: float
    temperature: float
    surge: float
    late_orders: int


class WorldState(BaseModel):
    simulation_minute: float = 0
    weather: WeatherState = Field(default_factory=WeatherState)
    traffic: TrafficState = Field(default_factory=TrafficState)
    orders: list[Order] = Field(default_factory=list)
    drivers: dict[str, DriverState] = Field(default_factory=dict)
    events: list[Disruption] = Field(default_factory=list)
    zones: dict[str, tuple[float, float]] = Field(default_factory=dict)


class SimulationState(BaseModel):
    running: bool = False
    scenario_seed: int
    simulation_minute: float = 0
    shift_minutes: int
    baseline: DriverState
    ai_driver: DriverState
    orders: list[Order] = Field(default_factory=list)
    weather: WeatherState
    traffic: TrafficState
    events: list[Disruption] = Field(default_factory=list)
    last_decisions: dict[str, Decision | None] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class JudgeEvent(BaseModel):
    event_type: EventType
    zone: str | None = None
    active: bool = True


class SocketMessage(BaseModel):
    type: str
    timestamp: int
    data: dict[str, Any]

