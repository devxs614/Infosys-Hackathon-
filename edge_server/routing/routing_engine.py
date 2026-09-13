"""Routing policy: fast external OSRM when available, local fallback otherwise."""
from __future__ import annotations

from edge_server.models import RouteEstimate, TrafficState, WeatherState
from edge_server.routing.fallback_router import FallbackRouter
from edge_server.routing.osrm_client import OSRMClient


class RoutingEngine:
    def __init__(self, osrm_url: str, use_osrm: bool = True) -> None:
        self.use_osrm = use_osrm
        self.osrm = OSRMClient(osrm_url)
        self.fallback = FallbackRouter()

    async def estimate(
        self, origin: tuple[float, float], destination: tuple[float, float], traffic: TrafficState,
        weather: WeatherState, destination_zone: str | None = None,
    ) -> RouteEstimate:
        if self.use_osrm:
            result = await self.osrm.route(origin, destination)
            if result is not None:
                rain_factor = 1 / .65 if weather.rain_intensity >= .8 else 1 + weather.rain_intensity * .25
                result.duration_minutes = round(result.duration_minutes * traffic.global_factor * rain_factor, 2)
                return result
        return self.fallback.estimate(origin, destination, traffic, weather, destination_zone)
