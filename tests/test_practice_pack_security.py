"""Local equivalent of the 14 deterministic Practice Pack cases."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from edge_server.main import create_app


CASES = [
    ("PP-001", {"sim_time": "10:20", "zone_dropoff": "Cumbres"}, "ACCEPT", None),
    ("PP-002", {"sim_time": "10:25", "zone_dropoff": "Mitras"}, "ACCEPT", None),
    ("PP-003", {"sim_time": "10:30", "zone_dropoff": "Obispado"}, "ACCEPT", None),
    ("PP-004", {"sim_time": "15:41", "courier_state_overrides": {"continuous_riding_min": 92}}, "SKIP", "heat_rule"),
    ("PP-005", {"sim_time": "15:43", "payout_mxn": 250, "courier_state_overrides": {"continuous_riding_min": 92}}, "SKIP", "heat_rule"),
    ("PP-006", {"sim_time": "17:00", "courier_state_overrides": {"continuous_riding_min": 246}}, "SKIP", "mandatory_break"),
    ("PP-007", {"sim_time": "10:00", "vehicle_type": "moto", "weight_kg": 24.0, "volume_l": 9.0}, "SKIP", "vehicle_capacity"),
    ("PP-008", {"sim_time": "10:00", "vehicle_type": "moto", "weight_kg": 3.5, "volume_l": 25.0}, "SKIP", "vehicle_capacity"),
    ("PP-009", {"sim_time": "10:00", "vehicle_type": "moto", "weight_kg": 19.0, "volume_l": 18.5}, "ACCEPT", None),
    ("PP-010", {"sim_time": "22:05", "zone_dropoff": {"id": 99, "name": "Independencia"}, "payout_mxn": 62}, "SKIP", "flagged_zone_night"),
    ("PP-011", {"sim_time": "22:06", "zone_dropoff": 99, "payout_mxn": 210, "surge_multiplier": 1.7}, "SKIP", "flagged_zone_night"),
    ("PP-012", {"sim_time": "22:07", "zone_dropoff": {"id": 8, "name": "Mitras"}}, "ACCEPT", None),
    ("PP-013", {"sim_time": "22:12", "prep_minutes": 6, "travel_minutes": 30, "courier_state_overrides": {"shift_end_time": "22:30"}}, "SKIP", "shift_end_infeasible"),
    ("PP-014", {"sim_time": "22:16", "prep_minutes": 2, "travel_minutes": 10, "courier_state_overrides": {"shift_end_time": "22:30"}}, "ACCEPT", None),
]


@pytest.mark.parametrize(("order_id", "data", "decision", "constraint"), CASES)
def test_practice_pack_security_contract(order_id, data, decision, constraint):
    with TestClient(create_app()) as client:
        response = client.post("/decide", json={"order_id": order_id, **data})

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["order_id"] == order_id
        assert result["decision"] == decision
        assert result["binding_constraint"] == constraint
        assert result["tier"] == "tier1"
        assert result["degraded"] is False
        assert result["latency_ms"] < 50
        assert len(result["reason"].split()) < 40

        explanation = client.get(f"/explain_decision/{order_id}")
        assert explanation.status_code == 200
        assert explanation.json()["decision"] == decision
        assert "inputs" in explanation.json()
        assert "alternatives_considered" in explanation.json()


def test_vehicle_profiles_apply_their_own_capacity_limits():
    with TestClient(create_app()) as client:
        car = client.post("/decide", json={"order_id": "CAR-CAPACITY", "sim_time": "14:00", "vehicle": "car", "weight_kg": 149, "volume_liters": 199})
        bike = client.post("/decide", json={"order_id": "BIKE-CAPACITY", "sim_time": "14:00", "vehicle": "bike", "weight_kg": 8.1, "volume_liters": 5})

        assert car.json()["decision"] == "ACCEPT"
        assert bike.json()["binding_constraint"] == "vehicle_capacity"


def test_protocol_shift_configuration_and_degraded_mode_do_not_change_fast_path_safety():
    with TestClient(create_app()) as client:
        configured = client.post("/protocol/shift-config", json={"seed": 1234, "shift_hours": 8, "vehicle": "bike", "start_location_zone": 7})
        assert configured.status_code == 200
        assert configured.json()["config"] == {"seed": 1234, "shift_hours": 8, "vehicle": "bike", "start_location_zone": 7}

        assert client.post("/protocol/degraded", json={"enabled": True}).json()["degraded"] is True
        decision = client.post("/decide", json={"order_id": "DEGRADED-SAFETY", "sim_time": "22:05", "zone_dropoff": 99, "vehicle": "moto"}).json()

        assert decision["decision"] == "SKIP"
        assert decision["binding_constraint"] == "flagged_zone_night"
        assert decision["degraded"] is True


def test_earlier_safety_constraints_remain_binding_when_shift_end_also_fails():
    with TestClient(create_app()) as client:
        result = client.post("/decide", json={
            "order_id": "FLAGGED-AND-LATE", "sim_time": "22:20", "zone_dropoff": 99,
            "vehicle": "moto", "restaurant_prep_min": 10, "estimated_pickup_min": 10,
            "estimated_delivery_min": 30,
            "courier_state_overrides": {"shift_end_time": "22:30"},
        }).json()

        assert result["decision"] == "SKIP"
        assert result["binding_constraint"] == "flagged_zone_night"
