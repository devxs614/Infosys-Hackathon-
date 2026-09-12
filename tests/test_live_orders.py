from fastapi.testclient import TestClient

from edge_server.main import create_app


def _next_message_of_type(socket, expected: str) -> dict:
    for _ in range(8):
        message = socket.receive_json()
        if message["type"] == expected:
            return message
    raise AssertionError(f"Did not receive {expected}")


def test_two_client_orders_produce_a_live_batch_and_driver_action():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _next_message_of_type(socket, "connection")
            _next_message_of_type(socket, "hello_response")
            _next_message_of_type(socket, "live_order_state")
            socket.send_json({"type": "NEW_ORDER", "client_id": "client_1", "location": [25.65, -100.36], "items": [{"id": "bowl"}]})
            order_one = _next_message_of_type(socket, "NEW_ORDER")
            assert order_one["data"]["order"]["client_id"] == "client_1"
            socket.send_json({"type": "NEW_ORDER", "client_id": "client_2", "location": [25.6517, -100.2892], "items": [{"id": "ramen"}]})
            _next_message_of_type(socket, "NEW_ORDER")
            batch = _next_message_of_type(socket, "AI_BATCH_SUGGESTION")
            assert set(batch["data"]["client_ids"]) == {"client_1", "client_2"}
            assert batch["data"]["savings_percent"] >= 0
            _next_message_of_type(socket, "DRIVER_NOTIFICATION")
            socket.send_json({"type": "DRIVER_ACTION", "action": "ACCEPT_BATCH"})
            action = _next_message_of_type(socket, "DRIVER_ACTION")
            assert action["data"]["batch"]["status"] == "ACCEPTED"


def test_live_order_rejects_coordinates_outside_demo_city():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _next_message_of_type(socket, "connection")
            _next_message_of_type(socket, "hello_response")
            _next_message_of_type(socket, "live_order_state")
            socket.send_json({"type": "NEW_ORDER", "client_id": "client_1", "location": [0, 0], "items": [{"id": "bowl"}]})
            error = _next_message_of_type(socket, "error")
            assert error["data"]["message"] == "Invalid NEW_ORDER"
