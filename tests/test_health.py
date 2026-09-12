from fastapi.testclient import TestClient

from edge_server.main import create_app


def test_health_is_available_without_integrations():
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["fallbacks"]["routing_fallback_available"] is True


def test_route_estimate_returns_a_monterrey_fallback_geometry_offline():
    with TestClient(create_app()) as client:
        response = client.post("/route/estimate", json={
            "origin": [25.6496, -100.3595],
            "destination": [25.6517, -100.2892],
        })
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["distance_km"] > 0
    assert len(payload["geometry"]) >= 2
