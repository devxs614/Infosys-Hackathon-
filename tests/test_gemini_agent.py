import pytest
from types import SimpleNamespace

from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.models import DecisionType, DriverState, TrafficState, WeatherState


def test_gemini_json_parser_accepts_fenced_json():
    decision = GeminiAgent.parse_decision('```json\n{"decision_type":"WAIT","selected_order_ids":[],"reasoning":"hold","estimated_profit_mxn":0,"estimated_distance_km":0,"estimated_duration_minutes":1,"confidence":0.8}\n```')
    assert decision.decision_type == DecisionType.WAIT


@pytest.mark.asyncio
async def test_gemini_without_key_uses_offline_fallback():
    decision = await GeminiAgent(enabled=True).decide(DriverState(driver_id="d", lat=25.6, lon=-100.3), [], TrafficState(), WeatherState(), 0, 240)
    assert decision.decision_type == DecisionType.WAIT


@pytest.mark.asyncio
async def test_auto_model_discovers_a_text_model_without_hardcoding_a_version():
    class FakeModels:
        used_model = ""

        def list(self):
            return [
                SimpleNamespace(name="models/gemini-image-example", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/gemini-3.6-flash", supported_actions=["generateContent"]),
            ]

        def generate_content(self, model, contents, config):
            self.used_model = model
            return SimpleNamespace(text='{"decision_type":"WAIT","selected_order_ids":[],"reasoning":"safe","estimated_profit_mxn":0,"estimated_distance_km":0,"estimated_duration_minutes":1,"confidence":0.9}')

    models = FakeModels()
    agent = GeminiAgent(api_key="test-key", model="auto", client=SimpleNamespace(models=models))
    decision = await agent.decide(DriverState(driver_id="d", lat=25.6, lon=-100.3), [], TrafficState(), WeatherState(), 0, 240)
    assert decision.decision_type == DecisionType.WAIT
    assert models.used_model == "gemini-3.6-flash"
