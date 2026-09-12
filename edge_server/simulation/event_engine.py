"""Translate active disruptions into world conditions, including judge-triggered events."""
from __future__ import annotations

from edge_server.models import Disruption, EventType, TrafficState, WeatherState


class EventEngine:
    def __init__(self) -> None:
        self.manual_events: list[Disruption] = []

    def trigger(self, event: Disruption) -> None:
        self.manual_events = [item for item in self.manual_events if item.event_type != event.event_type]
        self.manual_events.append(event)

    def all_active(self, automatic: list[Disruption]) -> list[Disruption]:
        combined = automatic + self.manual_events
        unique: dict[str, Disruption] = {item.id: item for item in combined if item.active}
        return list(unique.values())

    @staticmethod
    def conditions(events: list[Disruption]) -> tuple[WeatherState, TrafficState]:
        weather = WeatherState()
        traffic = TrafficState()
        for event in events:
            if event.event_type == EventType.EXTREME_HEAT:
                weather.temperature_c = 40
            elif event.event_type == EventType.TORRENTIAL_RAIN:
                weather.rain_intensity, weather.visibility, weather.flooding_risk = .95, .3, .7
                traffic.global_factor, traffic.congestion_level = 1.45, "severe"
            elif event.event_type == EventType.GONZALITOS_FLOOD:
                weather.flooding_risk = max(weather.flooding_risk, .9)
                traffic.global_factor = max(traffic.global_factor, 1.8)
                traffic.flooded_roads.append("Gonzalitos")
                traffic.affected_zones.append("Gonzalitos")
                traffic.congestion_level = "severe"
            elif event.event_type == EventType.SAN_PEDRO_CONGESTION:
                traffic.global_factor = max(traffic.global_factor, 1.55)
                traffic.affected_zones.append("San Pedro")
                traffic.congestion_level = "heavy"
            elif event.event_type == EventType.ROAD_CLOSURE:
                traffic.road_closures.append(event.zone)
                traffic.affected_zones.append(event.zone)
        return weather, traffic
