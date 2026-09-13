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


def _register_account(client: TestClient, name: str, email: str, role: str, vehicle: str | None = None) -> dict:
    response = client.post("/api/auth/register", json={
        "name": name, "email": email, "password": "correct-horse", "role": role, "vehicle": vehicle,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _bind(socket, account: dict, location: list[float] | None = None) -> None:
    socket.send_json({"type": "REGISTER_USER", "data": {
        "user_id": account["user"]["id"], "session_token": account["session_token"], "location": location,
    }})
    _receive_until(socket, "USER_REGISTERED")


def test_global_authentication_persists_in_the_pi_database_between_app_sessions(tmp_path, monkeypatch):
    database = tmp_path / "global-rumbo.sqlite3"
    monkeypatch.setenv("AUTH_DB_PATH", str(database))

    with TestClient(create_app()) as first_laptop:
        created = _register_account(first_laptop, "Juan", "juan@example.com", "client")

    with TestClient(create_app()) as second_laptop:
        login = second_laptop.post("/api/auth/login", json={"email": "juan@example.com", "password": "correct-horse"})
        assert login.status_code == 200
        assert login.json()["user"] == created["user"]
        assert login.json()["session_token"] != created["session_token"]


def test_real_driver_can_become_available_after_a_rejected_request_and_client_sees_the_same_person():
    with TestClient(create_app()) as client:
        customer = _register_account(client, "Sofía", "sofia@example.com", "client")
        driver = _register_account(client, "Carlos", "carlos@example.com", "driver", "Yamaha FZ")
        with client.websocket_connect("/ws") as customer_socket, client.websocket_connect("/ws") as driver_socket:
            _ready(customer_socket)
            _ready(driver_socket)
            _bind(customer_socket, customer)

            customer_socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": customer["user"]["id"], "session_token": customer["session_token"],
                "restaurant": "Tec", "origin": [25.6518, -100.2894], "destination": [25.6488, -100.3574],
                "destination_label": "Centrito Valle", "items": [{"id": "bowl", "quantity": 1}],
            }})
            _receive_until(customer_socket, "NO_DRIVERS_AVAILABLE")

            _bind(driver_socket, driver, [25.65, -100.35])
            _receive_until(driver_socket, "DRIVER_ONLINE")
            customer_socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": customer["user"]["id"], "session_token": customer["session_token"],
                "restaurant": "Tec", "origin": [25.6518, -100.2894], "destination": [25.6488, -100.3574],
                "destination_label": "Centrito Valle", "items": [{"id": "bowl", "quantity": 1}],
            }})
            pending = _receive_until(customer_socket, "NEW_ORDER")["data"]["order"]
            dispatched = _receive_until(driver_socket, "ORDER_DISPATCHED")["data"]
            assert dispatched["order"]["id"] == pending["id"]
            assert dispatched["driver"]["name"] == "Carlos"
            assert dispatched["driver"]["vehicle"] == "Yamaha FZ"

            driver_socket.send_json({"type": "DRIVER_ACTION", "data": {
                "action": "ACCEPT_ASSIGNMENT", "driver_id": driver["user"]["id"], "order_id": pending["id"],
                "session_token": driver["session_token"],
            }})
            matched = _receive_until(customer_socket, "ORDER_MATCHED")["data"]
            assert matched["driver"]["id"] == driver["user"]["id"]
            assert matched["driver"]["name"] == "Carlos"


def test_cancellation_is_broadcast_and_releases_the_real_courier_assignment():
    with TestClient(create_app()) as client:
        driver = _register_account(client, "Nora", "nora@example.com", "driver", "Moto eléctrica")
        customer = _register_account(client, "Mateo", "mateo@example.com", "client")
        with client.websocket_connect("/ws") as driver_socket, client.websocket_connect("/ws") as customer_socket:
            _ready(driver_socket)
            _ready(customer_socket)
            _bind(driver_socket, driver, [25.6551, -100.3781])
            _receive_until(driver_socket, "DRIVER_ONLINE")
            _bind(customer_socket, customer)
            customer_socket.send_json({"type": "NEW_ORDER", "data": {
                "client_id": customer["user"]["id"], "session_token": customer["session_token"],
                "restaurant": "Centrito", "origin": [25.6550, -100.3780], "destination": [25.6488, -100.3574],
                "destination_label": "Valle", "items": [{"id": "bowl", "quantity": 1}],
            }})
            order = _receive_until(customer_socket, "NEW_ORDER")["data"]["order"]
            _receive_until(driver_socket, "ORDER_DISPATCHED")
            customer_socket.send_json({"type": "CANCEL_ORDER", "data": {
                "client_id": customer["user"]["id"], "order_id": order["id"], "session_token": customer["session_token"],
            }})
            cancelled = _receive_until(driver_socket, "ORDER_CANCELLED")["data"]
            assert cancelled["order"]["status"] == "CANCELLED"
            assert cancelled["driver_id"] == driver["user"]["id"]
            state = _receive_until(driver_socket, "LIVE_ORDER_STATE")["data"]
            real_driver = next(item for item in state["drivers"] if item["id"] == driver["user"]["id"])
            assert order["id"] not in real_driver["assigned_order_ids"]
