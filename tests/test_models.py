from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from edge_server.models import Decision, DecisionType, Order


def test_order_and_decision_contracts():
    order = Order(id="O1", restaurant="Test", pickup_lat=25.6, pickup_lon=-100.3, dropoff_lat=25.7, dropoff_lon=-100.4,
                  payout_mxn=100, courier_payout_mxn=50, distance_km=2, estimated_minutes=12,
                  created_at=datetime.now(timezone.utc), pickup_deadline=10, delivery_deadline=30)
    assert order.status.value == "AVAILABLE"
    with pytest.raises(ValidationError):
        Decision(decision_type=DecisionType.ACCEPT, selected_order_ids=["O1", "O1"], reasoning="bad", estimated_profit_mxn=1, estimated_distance_km=1, estimated_duration_minutes=1, confidence=.5)

