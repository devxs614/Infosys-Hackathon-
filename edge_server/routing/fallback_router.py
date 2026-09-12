"""Offline-safe route estimates based on geodesic distance."""
from __future__ import annotations

import math

from edge_server.models import RouteEstimate, TrafficState, WeatherState


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0088
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi, d_lambda = math.radians(lat_b - lat_a), math.radians(lon_b - lon_a)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class FallbackRouter:
    """Approximate urban route distances without network access."""

    def __init__(self, average_speed_kmh: float = 24.0, street_factor: float = 1.22) -> None:
        self.average_speed_kmh = average_speed_kmh
        self.street_factor = street_factor

    def estimate(
        self, origin: tuple[float, float], destination: tuple[float, float], traffic: TrafficState,
        weather: WeatherState, destination_zone: str | None = None,
    ) -> RouteEstimate:
        straight_line = haversine_km(origin[0], origin[1], destination[0], destination[1])
        distance = straight_line * self.street_factor
        penalty = max(traffic.global_factor, 0.2)
        warnings: list[str] = ["offline fallback route"]
        if weather.rain_intensity > 0.3:
            penalty *= 1 + weather.rain_intensity * 0.35
            warnings.append("rain speed penalty")
        if weather.flooding_risk > 0.4:
            penalty *= 1 + weather.flooding_risk * 0.45
            warnings.append("flooding speed penalty")
        zone_closed = destination_zone and destination_zone in traffic.road_closures
        if zone_closed:
            return RouteEstimate(distance_km=distance, duration_minutes=0, geometry=[], feasible=False,
                                 warnings=warnings + [f"route to {destination_zone} is closed"])
        minutes = (distance / self.average_speed_kmh) * 60 * penalty
        return RouteEstimate(
            distance_km=round(distance, 3), duration_minutes=round(minutes, 2),
            geometry=[[origin[1], origin[0]], [destination[1], destination[0]]], warnings=warnings,
        )

