from edge_server.agents.decision_validator import DecisionValidator
from edge_server.models import Decision, DecisionType, DriverState, Order


def test_validator_rejects_unknown_order():
    decision = Decision(decision_type=DecisionType.ACCEPT, selected_order_ids=["unknown"], reasoning="test", estimated_profit_mxn=10, estimated_distance_km=1, estimated_duration_minutes=5, confidence=.8)
    result = DecisionValidator().validate(decision, DriverState(driver_id="d", lat=0, lon=0), [], 0, 20)
    assert not result.valid


def test_validator_accepts_feasible_known_order():
    order = Order(id="O1", restaurant="Test", pickup_lat=0, pickup_lon=0, dropoff_lat=.1, dropoff_lon=.1, payout_mxn=20,
                  courier_payout_mxn=10, distance_km=2, estimated_minutes=5, pickup_deadline=5, delivery_deadline=30)
    decision = Decision(decision_type=DecisionType.ACCEPT, selected_order_ids=["O1"], reasoning="test", estimated_profit_mxn=10, estimated_distance_km=2, estimated_duration_minutes=5, confidence=.8)
    assert DecisionValidator().validate(decision, DriverState(driver_id="d", lat=0, lon=0), [order], 0, 20).valid

