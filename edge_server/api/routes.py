"""Route projection endpoint backed by OSRM with an offline-safe fallback."""
from __future__ import annotations

from fastapi import APIRouter, Request

from edge_server.models import RouteRequest

router = APIRouter(prefix="/route", tags=["routing"])


@router.post("/estimate")
async def estimate_route(payload: RouteRequest, request: Request) -> dict:
    """Return street geometry as `[lon, lat]`, plus distance and traffic-aware ETA."""
    state = request.app.state.engine.state()
    estimate = await request.app.state.routing.estimate(
        tuple(payload.origin), tuple(payload.destination), state.traffic, state.weather,
    )
    return {
        "origin": payload.origin,
        "destination": payload.destination,
        "distance_km": estimate.distance_km,
        "eta_minutes": estimate.duration_minutes,
        "geometry": estimate.geometry,
        "street_names": estimate.street_names,
        "source": "osrm" if "offline fallback route" not in estimate.warnings else "fallback",
        "warnings": estimate.warnings,
    }
