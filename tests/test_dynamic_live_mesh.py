from fastapi.testclient import TestClient

from edge_server.main import create_app


def _receive_until(socket, expected: str) -> dict:
    for _ in range(12):
        message = socket.receive_json()
        if message["type"] == expected:
            return message
    raise AssertionError(f"Expected {expected}")


def test_dynamic_driver_is_assigned_to_a_dynamic_client_order():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({
                "type": "REGISTER_USER",
                "data": {"id": "driver-alex", "name": "Alex Rivera", "email": "alex@example.com", "role": "driver", "location": [25.67, -100.33]},
            })
            online = _receive_until(socket, "DRIVER_ONLINE")
            assert online["data"]["metrics"]["online_drivers_count"] == 1
            socket.send_json({
                "type": "NEW_ORDER",
                "data": {
                    "client_id": "client-sofia", "client_name": "Sofía Garza", "restaurant": "Rumbo Kitchen Tec",
                    "origin": [25.6518, -100.2894], "destination": [25.6488, -100.3574],
                    "destination_label": "Centrito Valle", "items": [{"id": "citrus-bowl", "quantity": 1}],
                },
            })
            order = _receive_until(socket, "NEW_ORDER")["data"]["order"]
            assert order["client_id"] == "client-sofia"
            assert order["driver_id"] == "driver-alex"
            assert order["status"] == "MATCHED"
            assert order["origin"] != order["destination"]
            socket.send_json({"type": "DRIVER_ACTION", "data": {"action": "ACCEPT_ASSIGNMENT", "driver_id": "driver-alex", "order_id": order["id"]}})
            action = _receive_until(socket, "DRIVER_ACTION")
            assert action["data"]["orders"][0]["status"] == "IN_TRANSIT"
