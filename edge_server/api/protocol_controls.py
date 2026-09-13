"""Additive controls used by the HackMTY judge presentation layer.

They are intentionally separate from authentication, live-order dispatch, and
the evaluator's `/decide` contract.  Configuration only changes the next
simulated demo shift; it never changes an active customer order.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/protocol", tags=["evaluation-protocol"])


class ShiftConfiguration(BaseModel):
    seed: int = Field(ge=0, le=2_147_483_647)
    shift_hours: float = Field(gt=0, le=16)
    vehicle: Literal["moto", "car", "bike"]
    start_location_zone: int = Field(ge=1, le=99)


class DegradedModeRequest(BaseModel):
    enabled: bool


@router.post("/shift-config")
async def configure_shift(payload: ShiftConfiguration, request: Request) -> dict:
    """Apply one deterministic configuration before the next demo is started."""
    config = await request.app.state.engine.configure_shift(
        seed=payload.seed,
        shift_hours=payload.shift_hours,
        vehicle=payload.vehicle,
        start_location_zone=payload.start_location_zone,
    )
    return {"status": "configured", "config": config}


@router.get("/shift-config")
async def get_shift_configuration(request: Request) -> dict:
    return request.app.state.engine.protocol_configuration()


@router.post("/degraded")
async def set_degraded_mode(payload: DegradedModeRequest, request: Request) -> dict:
    """Presentation-safe LLM failure drill; decisions remain on the fast path."""
    request.app.state.decision_degraded = payload.enabled
    return {"degraded": request.app.state.decision_degraded, "mode": "fast_path"}
