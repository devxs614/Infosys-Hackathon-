"""Shared API and simulation contracts. Values are intentionally JSON-friendly."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    SAN_PEDRO_CONGESTION = "SAN_PEDRO_CONGESTION"
    NORMAL_TRAFFIC = "NORMAL_TRAFFIC"
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
    street_names: list[str] = Field(default_factory=list)
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


class UserRegistration(BaseModel):
    """A centrally authenticated identity announced to the Edge node."""

    id: str = Field(min_length=3, max_length=100)
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    role: Literal["client", "driver", "admin"]
    location: list[float] | None = None
    vehicle: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)

    @field_validator("location")
    @classmethod
    def registered_location_is_local(cls, value: list[float] | None) -> list[float] | None:
        if value is not None:
            validate_monterrey_coordinates(value)
        return value


class AuthRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=3, max_length=256)
    role: Literal["client", "driver", "admin"]
    vehicle: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=3, max_length=256)


def validate_monterrey_coordinates(value: list[float]) -> list[float]:
    if len(value) != 2:
        raise ValueError("coordinates must be [lat, lon]")
    lat, lon = value
    if not 25.4 <= lat <= 26.0 or not -100.7 <= lon <= -99.9:
        raise ValueError("coordinates must be inside the Monterrey metropolitan demo area")
    return [float(lat), float(lon)]


class RouteRequest(BaseModel):
    origin: list[float] = Field(min_length=2, max_length=2)
    destination: list[float] = Field(min_length=2, max_length=2)

    @field_validator("origin", "destination")
    @classmethod
    def route_coordinates_are_local(cls, value: list[float]) -> list[float]:
        return validate_monterrey_coordinates(value)


class LiveOrderRequest(BaseModel):
    """Dynamic client-originated order contract with a legacy `location` adapter.

    `location` is retained only so the two original demo laptops continue working. New
    clients send `origin` and `destination`, both in `[lat, lon]` form.
    """

    client_id: str = Field(min_length=3, max_length=100)
    client_name: str = Field(default="Cliente Rumbo", min_length=2, max_length=120)
    restaurant: str = Field(default="Rumbo Kitchen", min_length=2, max_length=120)
    origin: list[float] | None = Field(default=None, min_length=2, max_length=2)
    destination: list[float] | None = Field(default=None, min_length=2, max_length=2)
    destination_label: str = Field(default="Destino Monterrey", min_length=2, max_length=160)
    location: list[float] | None = Field(default=None, min_length=2, max_length=2)
    items: list[dict[str, Any]] = Field(min_length=1, max_length=30)
    tip_mxn: float = Field(default=0, ge=0, le=500)
    weight_kg: float | None = Field(default=None, gt=0, le=200)
    volume_liters: float | None = Field(default=None, gt=0, le=500)

    @field_validator("origin", "destination", "location")
    @classmethod
    def monterrey_coordinates(cls, value: list[float] | None) -> list[float] | None:
        return validate_monterrey_coordinates(value) if value is not None else value

    @model_validator(mode="after")
    def normalize_legacy_location(self) -> "LiveOrderRequest":
        if self.destination is None and self.location is not None:
            self.destination = self.location
        if self.destination is None:
            raise ValueError("destination is required")
        if self.origin is None:
            self.origin = [25.6550, -100.3780]
        return self


class DriverActionRequest(BaseModel):
    action: Literal[
        "ACCEPT_BATCH", "ARRIVED_RESTAURANT", "DELIVERED_CLIENT_1", "DELIVERED_CLIENT_2",
        "ACCEPT_ASSIGNMENT", "START_DELIVERY", "DELIVERED",
        "DECLINE_ASSIGNMENT",
    ]
    driver_id: str | None = Field(default=None, min_length=3, max_length=100)
    order_id: str | None = Field(default=None, min_length=3, max_length=100)
    batch_id: str | None = Field(default=None, min_length=3, max_length=100)


class OrderCancellationRequest(BaseModel):
    """A client may cancel only its own undelivered order."""

    client_id: str = Field(min_length=3, max_length=100)
    order_id: str = Field(min_length=3, max_length=100)


class DriverTelemetryRequest(BaseModel):
    driver_id: str = Field(min_length=3, max_length=100)
    position: list[float] = Field(min_length=2, max_length=2)
    bearing: float = Field(default=0, ge=0, lt=360)
    street_name: str = Field(default="Monterrey", min_length=1, max_length=120)
    speed_kmh: float = Field(default=0, ge=0, le=160)

    @field_validator("position")
    @classmethod
    def telemetry_coordinates_are_local(cls, value: list[float]) -> list[float]:
        return validate_monterrey_coordinates(value)


class LiveOrder(BaseModel):
    id: str
    client_id: str
    client_name: str = "Cliente Rumbo"
    restaurant: str = "Rumbo Kitchen"
    origin: list[float] = Field(default_factory=lambda: [25.6550, -100.3780])
    destination: list[float] = Field(default_factory=lambda: [25.6866, -100.3161])
    destination_label: str = "Destino Monterrey"
    location: list[float]
    items: list[dict[str, Any]]
    status: str = "PENDING"
    driver_id: str | None = None
    batch_id: str | None = None
    distance_km: float = 0
    eta_minutes: float = 0
    delivery_fee_mxn: float = 0
    courier_payout_mxn: float = 0
    platform_commission_mxn: float = 0
    tip_mxn: float = 0
    weight_kg: float = 1.0
    volume_liters: float = 1.0
    declined_driver_ids: list[str] = Field(default_factory=list)
    route_geometry: list[list[float]] = Field(default_factory=list)
    courier_route_geometry: list[list[float]] = Field(default_factory=list)
    courier_distance_km: float = 0
    courier_eta_minutes: float = 0
    courier_street_names: list[str] = Field(default_factory=list)
    street_names: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class BatchPlan(BaseModel):
    id: str
    order_ids: list[str]
    client_ids: list[str]
    pickup: list[float]
    route: list[list[float]]
    individual_distance_km: float = Field(ge=0)
    batch_distance_km: float = Field(ge=0)
    savings_percent: float = Field(ge=0, le=100)
    reasoning: str
    status: str = "SUGGESTED"
    driver_id: str | None = None
    baseline_duration_minutes: float = 0
    optimized_duration_minutes: float = 0
    courier_earning_improvement_percent: float = 0
