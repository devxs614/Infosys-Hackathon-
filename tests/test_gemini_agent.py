import pytest

from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.models import DecisionType, DriverState, TrafficState, WeatherState


def test_gemini_json_parser_accepts_fenced_json():
    decision = GeminiAgent.parse_decision('```json\n{"decision_type":"WAIT","selected_order_ids":[],"reasoning":"hold","estimated_profit_mxn":0,"estimated_distance_km":0,"estimated_duration_minutes":1,"confidence":0.8}\n```')
    assert decision.decision_type == DecisionType.WAIT


@pytest.mark.asyncio
async def test_gemini_without_key_uses_offline_fallback():
    decision = await GeminiAgent(enabled=True).decide(DriverState(driver_id="d", lat=25.6, lon=-100.3), [], TrafficState(), WeatherState(), 0, 240)
    assert decision.decision_type == DecisionType.WAIT

