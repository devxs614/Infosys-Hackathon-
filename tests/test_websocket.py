from fastapi.testclient import TestClient

from edge_server.main import create_app


def test_websocket_sends_connection_and_hello():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            assert socket.receive_json()["type"] == "connection"
            hello = socket.receive_json()
            assert hello["type"] == "hello_response"
            assert "state" in hello["data"]

