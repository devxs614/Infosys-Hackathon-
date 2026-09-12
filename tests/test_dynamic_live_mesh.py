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


def test_match_financial_and_verdict_events_keep_the_public_driver_profile():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({
                "type": "REGISTER_USER",
                "data": {"id": "driver-rogelio", "name": "Rogelio Mendoza", "email": "rogelio@example.com", "role": "driver", "location": [25.65, -100.35]},
            })
            _receive_until(socket, "DRIVER_ONLINE")
            socket.send_json({
                "type": "NEW_ORDER",
                "data": {"client_id": "client-ana", "client_name": "Ana", "restaurant": "Centrito", "origin": [25.6496, -100.3595],
                         "destination": [25.6488, -100.3574], "destination_label": "Centrito Valle", "items": [{"id": "bowl", "price": 198}]},
            })
            match = _receive_until(socket, "ORDER_MATCHED")["data"]
            assert match["driver"]["name"] == "Rogelio Mendoza"
            assert match["driver"]["vehicle"] == "Honda Cargo 150"
            assert match["driver"]["rating"] == 4.9
            assert match["financials"]["current_trip_earnings_mxn"] > 0
            _receive_until(socket, "DRIVER_FINANCIAL_UPDATE")
            verdict = _receive_until(socket, "VERDICT_EVALUATION")["data"]
            assert verdict["available"] is False


def test_batch_emits_a_financial_impact_verdict():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({"type": "REGISTER_USER", "data": {"id": "driver-luis", "name": "Luis", "email": "luis@example.com", "role": "driver", "location": [25.65, -100.35]}})
            _receive_until(socket, "DRIVER_ONLINE")
            for client_id, destination in (("client-uno", [25.6488, -100.3574]), ("client-dos", [25.6517, -100.3492])):
                socket.send_json({"type": "NEW_ORDER", "data": {
                    "client_id": client_id, "client_name": client_id, "restaurant": "Centrito", "origin": [25.6496, -100.3595],
                    "destination": destination, "destination_label": "Valle", "items": [{"id": "bowl", "price": 198}],
                }})
                _receive_until(socket, "NEW_ORDER")
            verdict = _receive_until(socket, "VERDICT_EVALUATION")["data"]
            assert verdict["available"] is True
            assert verdict["baseline_distance_km"] >= verdict["optimized_distance_km"]
            assert verdict["courier_earning_improvement_percent"] > 0


def test_late_driver_registration_matches_pending_order_and_broadcasts_financials():
    """A courier coming online after checkout receives the same live match contract."""
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": "client-late", "client_name": "Mariana", "restaurant": "San Jeronimo",
                "origin": [25.6896, -100.3584], "destination": [25.6794, -100.3441],
                "destination_label": "Obispado", "items": [{"id": "bowl", "price": 198}],
            }})
            pending_order = _receive_until(socket, "NEW_ORDER")["data"]["order"]
            assert pending_order["status"] == "PENDING"

            socket.send_json({"type": "REGISTER_USER", "data": {
                "id": "driver-late", "name": "Rogelio Mendoza", "email": "late@example.com",
                "role": "driver", "location": [25.68, -100.35],
            }})
            _receive_until(socket, "DRIVER_ONLINE")
            match = _receive_until(socket, "ORDER_MATCHED")["data"]
            assert match["order"]["id"] == pending_order["id"]
            assert match["order"]["driver_id"] == "driver-late"
            assert match["driver"]["name"] == "Rogelio Mendoza"
            update = _receive_until(socket, "DRIVER_FINANCIAL_UPDATE")["data"]
            assert update["financials"]["driver_id"] == "driver-late"
            assert update["financials"]["current_trip_earnings_mxn"] > 0
            verdict = _receive_until(socket, "VERDICT_EVALUATION")["data"]
            assert verdict["available"] is False


def test_dispatch_chooses_the_closest_registered_driver_and_includes_approach_route():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            for driver_id, name, location in (
                ("driver-far", "Elena Lejana", [25.7210, -100.2800]),
                ("driver-near", "Carlos Cercano", [25.6552, -100.3775]),
            ):
                socket.send_json({"type": "REGISTER_USER", "data": {
                    "id": driver_id, "name": name, "email": f"{driver_id}@example.com", "role": "driver", "location": location,
                }})
                _receive_until(socket, "DRIVER_ONLINE")

            socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": "client-route", "client_name": "Mariana", "restaurant": "Centrito",
                "origin": [25.6550, -100.3780], "destination": [25.6488, -100.3574],
                "destination_label": "Centrito Valle", "items": [{"id": "bowl", "price": 198}],
            }})
            order = _receive_until(socket, "NEW_ORDER")["data"]["order"]
            assert order["driver_id"] == "driver-near"
            assert order["courier_route_geometry"]
            assert order["courier_distance_km"] >= 0
            match = _receive_until(socket, "ORDER_MATCHED")["data"]
            assert match["driver"]["name"] == "Carlos Cercano"


def test_cancelled_order_is_removed_from_the_assigned_courier_hud():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({"type": "REGISTER_USER", "data": {
                "id": "driver-cancel", "name": "Carlos", "email": "carlos@example.com", "role": "driver", "location": [25.6552, -100.3775],
            }})
            _receive_until(socket, "DRIVER_ONLINE")
            socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": "client-cancel", "client_name": "Mariana", "restaurant": "Centrito",
                "origin": [25.6550, -100.3780], "destination": [25.6488, -100.3574],
                "destination_label": "Centrito Valle", "items": [{"id": "bowl", "price": 198}],
            }})
            order = _receive_until(socket, "NEW_ORDER")["data"]["order"]
            socket.send_json({"type": "CANCEL_ORDER", "data": {"client_id": "client-cancel", "order_id": order["id"]}})
            cancelled = _receive_until(socket, "ORDER_CANCELLED")["data"]
            assert cancelled["order"]["status"] == "CANCELLED"
            assert cancelled["driver_id"] == "driver-cancel"
            state = _receive_until(socket, "LIVE_ORDER_STATE")["data"]
            driver = next(item for item in state["drivers"] if item["id"] == "driver-cancel")
            assert order["id"] not in driver["assigned_order_ids"]


def test_telemetry_cannot_create_an_unregistered_courier():
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as socket:
            _receive_until(socket, "live_order_state")
            socket.send_json({"type": "DRIVER_TELEMETRY", "data": {
                "driver_id": "driver-unknown", "position": [25.65, -100.35], "street_name": "Gonzalitos",
            }})
            error = _receive_until(socket, "error")
            assert "Register the courier" in error["data"]["message"]
