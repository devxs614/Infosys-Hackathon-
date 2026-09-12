import pytest

from edge_server.models import TrafficState, WeatherState
from edge_server.routing.fallback_router import FallbackRouter, haversine_km
from edge_server.routing.routing_engine import RoutingEngine


def test_haversine_and_fallback_route_are_usable_offline():
    assert haversine_km(25.6866, -100.3161, 25.6866, -100.3161) == 0
    route = FallbackRouter().estimate((25.68, -100.31), (25.69, -100.32), TrafficState(), WeatherState())
    assert route.feasible and route.distance_km > 0 and route.duration_minutes > 0


@pytest.mark.asyncio
async def test_routing_engine_uses_fallback_when_external_route_disabled():
    route = await RoutingEngine("https://example.invalid", use_osrm=False).estimate((25.68, -100.31), (25.69, -100.32), TrafficState(), WeatherState())
    assert "offline fallback route" in route.warnings

