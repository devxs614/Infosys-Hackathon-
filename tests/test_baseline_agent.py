import pytest

from edge_server.agents.baseline_agent import BaselineAgent
from edge_server.models import DriverState, Order, TrafficState, WeatherState


@pytest.mark.asyncio
async def test_baseline_accepts_a_good_current_offer():
    order = Order(id="O1", restaurant="Test", pickup_lat=25.6, pickup_lon=-100.3, dropoff_lat=25.61, dropoff_lon=-100.31,
                  payout_mxn=150, courier_payout_mxn=90, distance_km=2, estimated_minutes=12, pickup_deadline=20, delivery_deadline=50)
    decision = await BaselineAgent().decide(DriverState(driver_id="d", lat=25.6, lon=-100.3), [order], TrafficState(), WeatherState(), 0, 240)
    assert decision.decision_type.value == "ACCEPT"
    assert decision.selected_order_ids == ["O1"]

