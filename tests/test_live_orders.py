from fastapi.testclient import TestClient

from edge_server.main import create_app


def _receive_until(socket, expected: str, limit: int = 30) -> dict:
    for _ in range(limit):
        message = socket.receive_json()
        if message["type"] == expected:
            return message
    raise AssertionError(f"Expected {expected}")


def _ready(socket) -> None:
    _receive_until(socket, "connection")
    _receive_until(socket, "hello_response")
    _receive_until(socket, "live_order_state")


def _account(client: TestClient, *, name: str, email: str, role: str, vehicle: str | None = None) -> dict:
    response = client.post("/api/auth/register", json={
        "name": name, "email": email, "password": "secure-pass", "role": role, "vehicle": vehicle,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _register_socket(socket, account: dict, location: list[float] | None = None) -> None:
    socket.send_json({"type": "REGISTER_USER", "data": {
        "user_id": account["user"]["id"], "session_token": account["session_token"], "location": location,
    }})
    _receive_until(socket, "USER_REGISTERED")


def _new_order(socket, customer: dict, destination: list[float] = [25.6488, -100.3574]) -> None:
    socket.send_json({"type": "NEW_ORDER", "data": {
        "client_id": customer["user"]["id"], "session_token": customer["session_token"],
        "restaurant": "Centrito", "origin": [25.6550, -100.3780], "destination": destination,
        "destination_label": "Centrito Valle", "items": [{"id": "bowl", "quantity": 1}],
    }})


def test_orders_without_a_live_registered_driver_remain_pending_and_are_not_invented():
    with TestClient(create_app()) as client:
        customer = _account(client, name="Mariana", email="mariana@example.com", role="client")
        with client.websocket_connect("/ws") as customer_socket:
            _ready(customer_socket)
            _register_socket(customer_socket, customer)
            _new_order(customer_socket, customer)

            order = _receive_until(customer_socket, "NEW_ORDER")["data"]["order"]
            unavailable = _receive_until(customer_socket, "NO_DRIVERS_AVAILABLE")["data"]

            assert order["status"] == "PENDING"
            assert order["driver_id"] is None
            assert unavailable["status"] == "NO_DRIVERS_AVAILABLE"
            assert unavailable["message"] == "No hay repartidores disponibles en este momento"


def test_order_rejects_an_address_outside_the_twenty_kilometre_service_radius():
    with TestClient(create_app()) as client:
        customer = _account(client, name="Elena", email="elena@example.com", role="client")
        with client.websocket_connect("/ws") as customer_socket:
            _ready(customer_socket)
            _register_socket(customer_socket, customer)
            _new_order(customer_socket, customer, destination=[25.45, -100.05])
            error = _receive_until(customer_socket, "error")
            assert error["data"]["message"] == "La dirección de entrega excede el límite operativo de 20 km"


def test_only_the_targeted_real_courier_can_accept_its_dispatched_order():
    with TestClient(create_app()) as client:
        topo = _account(client, name="Topo", email="topo@example.com", role="driver", vehicle="Bicicleta eléctrica")
        other = _account(client, name="Luz", email="luz@example.com", role="driver", vehicle="Moto")
        customer = _account(client, name="Ana", email="ana@example.com", role="client")

        with client.websocket_connect("/ws") as topo_socket, client.websocket_connect("/ws") as other_socket, client.websocket_connect("/ws") as customer_socket:
            _ready(topo_socket)
            _ready(other_socket)
            _ready(customer_socket)
            _register_socket(topo_socket, topo, [25.6551, -100.3781])
            _receive_until(topo_socket, "DRIVER_ONLINE")
            _register_socket(other_socket, other, [25.72, -100.28])
            _receive_until(other_socket, "DRIVER_ONLINE")
            _register_socket(customer_socket, customer)

            _new_order(customer_socket, customer)
            order = _receive_until(customer_socket, "NEW_ORDER")["data"]["order"]
            dispatch = _receive_until(topo_socket, "ORDER_DISPATCHED")["data"]

            assert order["status"] == "PENDING"
            assert order["driver_id"] == topo["user"]["id"]
            assert dispatch["driver"]["id"] == topo["user"]["id"]
            assert dispatch["driver"]["name"] == "Topo"
            assert dispatch["driver"]["vehicle"] == "Bicicleta eléctrica"
            assert "rating" not in dispatch["driver"]

            other_socket.send_json({"type": "DRIVER_ACTION", "data": {
                "action": "ACCEPT_ASSIGNMENT", "driver_id": other["user"]["id"],
                "order_id": order["id"], "session_token": other["session_token"],
            }})
            denied = _receive_until(other_socket, "error")
            assert denied["data"]["message"] == "This courier is not assigned to the selected order"

            topo_socket.send_json({"type": "DRIVER_ACTION", "data": {
                "action": "ACCEPT_ASSIGNMENT", "driver_id": topo["user"]["id"],
                "order_id": order["id"], "session_token": topo["session_token"],
            }})
            match = _receive_until(customer_socket, "ORDER_MATCHED")["data"]
            assert match["order"]["status"] == "MATCHED"
            assert match["driver"]["name"] == "Topo"
            assert match["driver"]["vehicle"] == "Bicicleta eléctrica"
