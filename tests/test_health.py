from fastapi.testclient import TestClient

from edge_server.main import create_app


def test_health_is_available_without_integrations():
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["fallbacks"]["routing_fallback_available"] is True

