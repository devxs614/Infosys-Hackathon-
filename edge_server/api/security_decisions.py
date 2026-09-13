"""Deterministic, isolated safety decisions for the Practice Pack contract.

This router deliberately has no dependency on the live demo state.  It exposes
the evaluator-facing contract without changing authenticated users, dispatch,
WebSockets, persistence, or any UI-facing route.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator


router = APIRouter(tags=["practice-pack-security"])

# The names are intentionally public and exact: the Practice Pack identifies
# Zone 99 by both its id and this full convention name.
FLAGGED_ZONES: dict[int, str] = {
    99: "Zona 99 (Flagged Zone - Convención Practice Pack / Independencia)",
    13: "San Bernabé / Topo Chico",
    15: "La Campana / Altamira",
    22: "Escobedo Norte / Alianza",
    31: "Rincón de la Sierra / Juarez Sector 4",
}

_FLAGGED_ZONE_TOKENS = {
    "zona 99", "flagged zone", "independencia", "san bernabé", "topo chico",
    "la campana", "altamira", "escobedo norte", "alianza", "rincón de la sierra",
    "rincon de la sierra", "juarez sector 4",
}
_CONSTRAINTS = {
    "flagged_zone_night", "heat_rule", "mandatory_break", "vehicle_capacity", "shift_end_infeasible",
}


class CourierStateOverrides(BaseModel):
    """Per-evaluation values; these never mutate central courier state."""

    model_config = ConfigDict(extra="allow")

    continuous_riding_min: float | None = Field(default=None, ge=0)
    shift_elapsed_hours: float | None = Field(default=None, ge=0)
    last_break_end_time: str | float | int | None = None
    shift_end_time: str | float | int | None = None
    in_flight_orders: list[Any] | None = None


class DecideRequest(BaseModel):
    """Accept the evaluator fields plus harmless aliases used by demo fixtures."""

    model_config = ConfigDict(extra="allow")

    order_id: str = Field(min_length=1)
    sim_time: str | float | int = "00:00"
    zone_dropoff: Any = None
    courier_state_overrides: CourierStateOverrides = Field(default_factory=CourierStateOverrides)

    @model_validator(mode="before")
    @classmethod
    def _flatten_order_fixture(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        nested_order = data.get("order")
        if isinstance(nested_order, dict):
            for key, nested_value in nested_order.items():
                data.setdefault(key, nested_value)
        data.setdefault("order_id", data.get("id"))
        return data


def _value(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = data.get(name)
        if value is not None:
            return value
    return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _minutes(value: Any) -> float:
    """Normalise HH:MM, decimal-hours, or elapsed-minute test fixtures."""
    if isinstance(value, str):
        text = value.strip()
        if ":" in text:
            hour, minute = text.split(":", 1)
            return (_number(hour) * 60 + _number(minute)) % (24 * 60)
        value = text
    numeric = _number(value)
    # Values in [0, 24] are interpreted as decimal hours. Larger values are
    # already minute-of-day values, matching simulation fixtures.
    return numeric * 60 if 0 <= numeric <= 24 else numeric % (24 * 60)


def _is_flagged_zone(zone: Any) -> bool:
    if isinstance(zone, dict):
        for key in ("id", "zone_id", "zoneId"):
            if str(zone.get(key, "")).strip() in {str(item) for item in FLAGGED_ZONES}:
                return True
        zone = " ".join(str(value) for value in zone.values())
    text = str(zone or "").strip().lower()
    if text in {str(item) for item in FLAGGED_ZONES}:
        return True
    return any(token in text for token in _FLAGGED_ZONE_TOKENS)


def _required_minutes(data: dict[str, Any]) -> float:
    prep = _number(_value(data, "prep_minutes", "prep_time_min", "prep_time_minutes", "prep_min"))
    travel = _number(_value(
        data, "travel_minutes", "travel_time_min", "estimated_travel_minutes",
        "route_minutes", "estimated_minutes", "delivery_minutes",
    ))
    return max(0.0, prep) + max(0.0, travel)


def _evaluate(request: DecideRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate fixed safety constraints in deterministic, safety-first order."""
    raw = request.model_dump(mode="json")
    overrides = request.courier_state_overrides.model_dump(mode="json", exclude_none=True)
    for key, value in overrides.items():
        # Overrides are intentionally scoped to this local evaluation only.
        raw[key] = value

    sim_minutes = _minutes(_value(raw, "sim_time", "simulation_time"))
    continuous_riding = _number(_value(raw, "continuous_riding_min", "continuous_riding_minutes"))
    shift_end = _value(raw, "shift_end_time")
    required_minutes = _required_minutes(raw)
    vehicle = str(_value(raw, "vehicle_type", "vehicle", default="moto")).strip().lower()
    weight_kg = _number(_value(raw, "weight_kg", "package_weight_kg", "order_weight_kg", "weight"))
    volume_l = _number(_value(raw, "volume_l", "package_volume_l", "order_volume_l", "volume"))

    constraint: str | None = None
    reason = "Order meets the current courier safety and capacity constraints."
    if sim_minutes >= 22 * 60 and _is_flagged_zone(request.zone_dropoff):
        constraint = "flagged_zone_night"
        reason = "Flagged safety zone after 22:00; night delivery skipped for safety."
    elif continuous_riding >= 240:
        constraint = "mandatory_break"
        reason = "Mandatory break: 4 h of continuous riding reached before accepting another order."
    elif 12 * 60 <= sim_minutes <= 16 * 60 and continuous_riding > 90:
        constraint = "heat_rule"
        reason = "Heat safety rule: continuous riding exceeds 90 minutes during the 12:00 cooling window."
    elif vehicle in {"moto", "motorcycle", "motorbike"} and weight_kg > 20.0:
        constraint = "vehicle_capacity"
        reason = "Vehicle capacity exceeded: package weight is above the moto 20 kg limit."
    elif vehicle in {"moto", "motorcycle", "motorbike"} and volume_l > 20.0:
        constraint = "vehicle_capacity"
        reason = "Vehicle capacity exceeded: package volume is above the moto 20 liter limit."
    elif shift_end is not None and sim_minutes + required_minutes > _minutes(shift_end):
        constraint = "shift_end_infeasible"
        reason = "Shift end infeasible: required time exceeds the minutes remaining before shift end."

    assert constraint is None or constraint in _CONSTRAINTS
    decision = "SKIP" if constraint else "ACCEPT"
    inputs = {
        "sim_time": request.sim_time,
        "zone_dropoff": request.zone_dropoff,
        "continuous_riding_min": continuous_riding,
        "shift_elapsed_hours": _value(raw, "shift_elapsed_hours"),
        "last_break_end_time": _value(raw, "last_break_end_time"),
        "shift_end_time": shift_end,
        "in_flight_orders": _value(raw, "in_flight_orders", default=[]),
        "vehicle_type": vehicle,
        "weight_kg": weight_kg,
        "volume_l": volume_l,
        "required_minutes": required_minutes,
    }
    result = {
        "order_id": request.order_id,
        "decision": decision,
        "reason": reason,
        "binding_constraint": constraint,
        "tier": "tier1",
        "degraded": False,
    }
    explanation = {
        "order_id": request.order_id,
        "decision": decision,
        "reason": reason,
        "inputs": inputs,
        "alternatives_considered": [
            {
                "decision": "ACCEPT",
                "available": constraint is None,
                "reason": "Blocked by the binding safety constraint." if constraint else "All safety constraints passed.",
            }
        ],
    }
    return result, explanation


@router.post("/decide")
async def decide(payload: DecideRequest, request: Request) -> dict[str, Any]:
    """Return a sub-50ms local safety decision without touching live dispatch."""
    started_at = perf_counter()
    result, explanation = _evaluate(payload)
    request.app.state.decision_explanations[payload.order_id] = explanation
    result["latency_ms"] = round((perf_counter() - started_at) * 1000, 3)
    return result


@router.get("/explain_decision/{order_id}")
async def explain_decision(order_id: str, request: Request) -> dict[str, Any]:
    """Retrieve the last evaluator-facing explanation for one order id."""
    explanation = request.app.state.decision_explanations.get(order_id)
    if explanation is None:
        raise HTTPException(status_code=404, detail="Decision explanation not found")
    return explanation
