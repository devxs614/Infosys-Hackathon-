"""Additive controls used by the HackMTY judge presentation layer.

They are intentionally separate from authentication, live-order dispatch, and
the evaluator's `/decide` contract.  Configuration only changes the next
simulated demo shift; it never changes an active customer order.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from edge_server.models import EventType, JudgeEvent


router = APIRouter(prefix="/protocol", tags=["evaluation-protocol"])


class ShiftConfiguration(BaseModel):
    seed: int = Field(ge=0, le=2_147_483_647)
    shift_hours: float = Field(gt=0, le=16)
    vehicle: Literal["moto", "car", "bike"]
    start_location_zone: int = Field(ge=1, le=99)


class DegradedModeRequest(BaseModel):
    enabled: bool


class TimeSyncRequest(BaseModel):
    simulated_minutes: float | None = Field(default=None, ge=0, lt=1440)
    paused: bool | None = None


class ShockRequest(BaseModel):
    shock: Literal["surge", "closure", "rain", "delay", "normal"]
    zone: str | None = Field(default=None, max_length=120)


class RoadClosureRequest(BaseModel):
    position: list[float] = Field(min_length=2, max_length=2)
    label: str | None = Field(default=None, max_length=120)


class DriverDelayRequest(BaseModel):
    driver_id: str = Field(min_length=3, max_length=100)
    minutes: float = Field(default=15, gt=0, le=120)


_SHOCK_EVENTS = {
    "surge": EventType.SAN_PEDRO_SURGE,
    "closure": EventType.ROAD_CLOSURE,
    "rain": EventType.TORRENTIAL_RAIN,
    "delay": EventType.SAN_PEDRO_CONGESTION,
    "normal": EventType.NORMAL_TRAFFIC,
}


async def publish_control_state(request: Request) -> dict:
    """Broadcast one Pi-owned snapshot to every browser without local fallbacks."""
    state = await request.app.state.protocol_state.snapshot()
    await request.app.state.connections.broadcast("TIME_SYNC_UPDATE", state)
    return state


async def apply_shock(request: Request, shock: str, zone: str | None = None) -> dict:
    """Keep environmental controls, simulator conditions, and live dispatch aligned."""
    event_type = _SHOCK_EVENTS[shock]
    await request.app.state.protocol_state.update_shock(None if shock == "normal" else shock, zone)
    await request.app.state.engine.trigger(JudgeEvent(event_type=event_type, zone=zone))
    state = request.app.state.engine.state()
    batch = await request.app.state.live_orders.recalculate(event_type.value, state.traffic, state.weather)
    if batch:
        await request.app.state.connections.broadcast("AI_BATCH_SUGGESTION", batch.model_dump(mode="json"))
        await request.app.state.connections.broadcast("AI_BATCH_OPTIMIZATION", batch.model_dump(mode="json"))
    await request.app.state.connections.broadcast("LIVE_ORDER_STATE", request.app.state.live_orders.snapshot())
    return await publish_control_state(request)


@router.post("/shift-config")
async def configure_shift(payload: ShiftConfiguration, request: Request) -> dict:
    """Apply one deterministic configuration before the next demo is started."""
    config = await request.app.state.engine.configure_shift(
        seed=payload.seed,
        shift_hours=payload.shift_hours,
        vehicle=payload.vehicle,
        start_location_zone=payload.start_location_zone,
    )
    await request.app.state.protocol_state.update_time({"simulated_minutes": 14 * 60, "paused": True})
    await publish_control_state(request)
    return {"status": "configured", "config": config}


@router.get("/shift-config")
async def get_shift_configuration(request: Request) -> dict:
    return request.app.state.engine.protocol_configuration()


@router.post("/degraded")
async def set_degraded_mode(payload: DegradedModeRequest, request: Request) -> dict:
    """Presentation-safe LLM failure drill; decisions remain on the fast path."""
    request.app.state.decision_degraded = payload.enabled
    return {"degraded": request.app.state.decision_degraded, "mode": "fast_path"}


@router.get("/time-sync")
async def get_time_sync(request: Request) -> dict:
    return await request.app.state.protocol_state.snapshot()


@router.post("/time-sync")
async def update_time_sync(payload: TimeSyncRequest, request: Request) -> dict:
    state = await request.app.state.protocol_state.update_time(payload.model_dump(exclude_none=True))
    await request.app.state.live_orders.apply_control_state(state)
    await request.app.state.connections.broadcast("TIME_SYNC_UPDATE", state)
    return state


@router.post("/shock")
async def update_shock(payload: ShockRequest, request: Request) -> dict:
    return await apply_shock(request, payload.shock, payload.zone)


@router.post("/road-closure")
async def pin_road_closure(payload: RoadClosureRequest, request: Request) -> dict:
    state = await request.app.state.protocol_state.add_road_closure(payload.position, payload.label)
    await request.app.state.live_orders.apply_control_state(state)
    await request.app.state.engine.trigger(JudgeEvent(event_type=EventType.ROAD_CLOSURE, zone=payload.label or "Pinned closure"))
    engine_state = request.app.state.engine.state()
    await request.app.state.live_orders.recalculate("ROAD_CLOSURE", engine_state.traffic, engine_state.weather)
    await request.app.state.connections.broadcast("LIVE_ORDER_STATE", request.app.state.live_orders.snapshot())
    await request.app.state.connections.broadcast("TIME_SYNC_UPDATE", state)
    return state


@router.post("/driver-delay")
async def delay_driver(payload: DriverDelayRequest, request: Request) -> dict:
    state = await request.app.state.protocol_state.delay_driver(payload.driver_id, payload.minutes)
    driver = await request.app.state.live_orders.apply_driver_delay(payload.driver_id, payload.minutes)
    await request.app.state.connections.broadcast("DRIVER_DELAYED", {"driver": driver, "minutes": payload.minutes})
    await request.app.state.connections.broadcast("LIVE_ORDER_STATE", request.app.state.live_orders.snapshot())
    await request.app.state.connections.broadcast("TIME_SYNC_UPDATE", state)
    return {"driver": driver, "control": state}


@router.post("/full-autonomous-demo")
async def launch_full_autonomous_demo(request: Request) -> dict:
    """Explicit, in-memory judge demo; it never creates SQLite user records."""
    snapshot = await request.app.state.live_orders.launch_full_demo()
    await request.app.state.connections.broadcast("LIVE_ORDER_STATE", snapshot)
    await request.app.state.connections.broadcast("FULL_AUTONOMOUS_DEMO", {
        "clients": 15, "couriers": 7, "message": "Full autonomous demo launched on the Pi.",
    })
    return {"status": "started", "clients": 15, "couriers": 7, "state": snapshot}
