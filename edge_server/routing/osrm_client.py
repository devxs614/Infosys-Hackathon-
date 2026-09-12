"""Short-timeout OSRM HTTP client. Failure returns None for local fallback."""
from __future__ import annotations

import logging

import httpx

from edge_server.models import RouteEstimate

logger = logging.getLogger(__name__)


class OSRMClient:
    def __init__(self, base_url: str, timeout_seconds: float = 0.35) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> RouteEstimate | None:
        coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = f"{self.base_url}/route/v1/driving/{coordinates}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"})
                response.raise_for_status()
            route = response.json().get("routes", [None])[0]
            if not route:
                return None
            geometry = route.get("geometry", {}).get("coordinates", [])
            street_names = [step.get("name") for leg in route.get("legs", []) for step in leg.get("steps", []) if step.get("name")]
            return RouteEstimate(distance_km=route["distance"] / 1000, duration_minutes=route["duration"] / 60,
                                 geometry=geometry, street_names=list(dict.fromkeys(street_names)), warnings=[])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning("OSRM unavailable, using fallback: %s", exc.__class__.__name__)
            return None
