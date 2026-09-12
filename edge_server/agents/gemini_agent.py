"""Gemini strategic-agent adapter with deterministic offline fallback."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from edge_server.agents.base_agent import BaseAgent
from edge_server.agents.prompts import SYSTEM_PROMPT
from edge_server.models import Decision, DecisionType, DriverState, Order, TrafficState, WeatherState

logger = logging.getLogger(__name__)


class GeminiAgent(BaseAgent):
    """Ask Gemini for strategy but preserve deterministic behaviour when it is unavailable."""

    agent_name = "gemini"

    def __init__(self, api_key: str = "", model: str = "auto", enabled: bool = True, client: Any | None = None) -> None:
        self.api_key = api_key
        self.model = model.strip() or "auto"
        self._resolved_model: str | None = None
        self.enabled = enabled and bool(api_key)
        self.client = client
        if self.enabled and self.client is None:
            try:
                from google import genai  # Imported lazily: app runs without the SDK/API key.
                self.client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("Gemini unavailable, using fallback agent: %s", exc.__class__.__name__)
                self.enabled = False

    def _context(self, driver: DriverState, orders: list[Order], traffic: TrafficState, weather: WeatherState,
                 simulation_minute: float, time_remaining: float) -> str:
        return json.dumps({
            "driver": driver.model_dump(mode="json"), "available_orders": [o.model_dump(mode="json") for o in orders],
            "traffic": traffic.model_dump(), "weather": weather.model_dump(), "simulation_minute": simulation_minute,
            "time_remaining_minutes": time_remaining,
        }, separators=(",", ":"))

    @staticmethod
    def parse_decision(payload: str | dict[str, Any]) -> Decision:
        """Parse only a JSON object; markdown fences from models are tolerated."""
        if isinstance(payload, str):
            cleaned = payload.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            payload = json.loads(cleaned)
        return Decision.model_validate(payload)

    async def _resolve_model(self) -> str:
        """Use an explicitly configured model or discover a current text model safely.

        `auto` avoids hardcoding a version that may disappear before the hackathon. Discovery
        happens only after a real API key has been configured and failures retain the local fallback.
        """
        if self.model.lower() != "auto":
            return self.model
        if self._resolved_model:
            return self._resolved_model
        if self.client is None:
            raise RuntimeError("Gemini client unavailable")

        def find_model() -> str:
            candidates: list[str] = []
            for item in self.client.models.list():
                name = str(getattr(item, "name", "")).removeprefix("models/")
                actions = [str(action).lower() for action in (getattr(item, "supported_actions", None) or [])]
                unsuitable = ("image", "audio", "tts", "live", "robotics", "embedding")
                if name.startswith("gemini-") and "generatecontent" in actions and not any(term in name.lower() for term in unsuitable):
                    candidates.append(name)
            if not candidates:
                raise RuntimeError("No compatible Gemini text model is available to this API key")
            def priority(name: str) -> tuple[bool, tuple[int, ...], str]:
                """Prefer the highest current Flash generation without naming one explicitly."""
                version = tuple(int(value) for value in re.findall(r"\d+", name))
                return "flash" in name.lower(), version, name.lower()

            # Prefer a fast, edge-demo-suitable model and then the newest generation returned by Google.
            return max(candidates, key=priority)

        self._resolved_model = await asyncio.to_thread(find_model)
        logger.info("Gemini model discovered successfully")
        return self._resolved_model

    async def _ask_gemini(self, context: str) -> Decision:
        if self.client is None:
            raise RuntimeError("Gemini client unavailable")
        model = await self._resolve_model()

        def generate() -> Any:
            return self.client.models.generate_content(
                model=model,
                contents=f"{SYSTEM_PROMPT}\n\nWORLD_STATE_JSON:\n{context}",
                config={"response_mime_type": "application/json"},
            )

        response = await asyncio.to_thread(generate)
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return self.parse_decision(parsed)
        return self.parse_decision(getattr(response, "text", ""))

    @staticmethod
    def _value(order: Order, traffic: TrafficState, weather: WeatherState) -> float:
        heat_penalty = 1.08 if weather.temperature_c >= 39 else 1.0
        duration = order.estimated_minutes * traffic.global_factor * (1 + weather.rain_intensity * .2) * heat_penalty
        risk = max(0.0, 10 - (order.delivery_deadline - duration)) * .8
        return order.courier_payout_mxn * order.surge_multiplier * 60 / max(duration, 1) - risk

    def fallback_decide(self, driver: DriverState, orders: list[Order], traffic: TrafficState, weather: WeatherState,
                        simulation_minute: float, time_remaining: float) -> Decision:
        """Strategic deterministic policy used in every no-credential/offline demo.

        Unlike the baseline it can choose compatible two-order batches and move to a known
        high-demand zone after checking conditions. It sees no data that the baseline cannot see.
        """
        viable = [o for o in orders if o.delivery_deadline > simulation_minute + 2 and o.estimated_minutes <= time_remaining]
        if not viable or not driver.available:
            return Decision(decision_type=DecisionType.WAIT, reasoning="Holding position until a feasible offer appears.",
                            estimated_profit_mxn=0, estimated_distance_km=0, estimated_duration_minutes=1, confidence=.9)
        ordered = sorted(viable, key=lambda o: self._value(o, traffic, weather), reverse=True)
        first = ordered[0]
        compatible = next((other for other in ordered[1:] if other.zone == first.zone and
                           first.estimated_minutes + other.estimated_minutes * .55 <= time_remaining and
                           min(first.delivery_deadline, other.delivery_deadline) > simulation_minute + first.estimated_minutes), None)
        if compatible and self._value(first, traffic, weather) + self._value(compatible, traffic, weather) > self._value(first, traffic, weather) * 1.45:
            distance = first.distance_km + compatible.distance_km * .62
            duration = (first.estimated_minutes + compatible.estimated_minutes * .62) * traffic.global_factor
            return Decision(decision_type=DecisionType.BATCH, selected_order_ids=[first.id, compatible.id],
                            reasoning="Compatible pickups in the same zone improve paid time while maintaining both deadlines.",
                            estimated_profit_mxn=first.courier_payout_mxn + compatible.courier_payout_mxn,
                            estimated_distance_km=distance, estimated_duration_minutes=duration, confidence=.83)
        if first.zone in traffic.road_closures:
            return Decision(decision_type=DecisionType.WAIT, reasoning="Top offer is in a closed zone; preserve capacity for a feasible route.",
                            estimated_profit_mxn=0, estimated_distance_km=0, estimated_duration_minutes=1, confidence=.88)
        if first.surge_multiplier >= 1.5 or self._value(first, traffic, weather) >= 55:
            return Decision(decision_type=DecisionType.ACCEPT, selected_order_ids=[first.id],
                            reasoning="Selected best risk-adjusted hourly offer, accounting for current conditions and surge.",
                            estimated_profit_mxn=first.courier_payout_mxn, estimated_distance_km=first.distance_km,
                            estimated_duration_minutes=first.estimated_minutes * traffic.global_factor, confidence=.81)
        return Decision(decision_type=DecisionType.REPOSITION, reasoning="Low current value; reposition toward San Pedro demand instead of accepting a weak offer.",
                        estimated_profit_mxn=0, estimated_distance_km=3.0, estimated_duration_minutes=9, confidence=.7,
                        reposition_lat=25.6605, reposition_lon=-100.4030)

    async def decide(self, driver: DriverState, orders: list[Order], traffic: TrafficState, weather: WeatherState,
                     simulation_minute: float, time_remaining: float) -> Decision:
        if self.enabled:
            try:
                return await self._ask_gemini(self._context(driver, orders, traffic, weather, simulation_minute, time_remaining))
            except Exception as exc:
                logger.warning("Gemini unavailable or invalid, using fallback agent: %s", exc.__class__.__name__)
        return self.fallback_decide(driver, orders, traffic, weather, simulation_minute, time_remaining)
