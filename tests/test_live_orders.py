import asyncio

import pytest
from fastapi.testclient import TestClient

from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.live_order_service import LiveOrderCoordinator
from edge_server.main import create_app
from edge_server.models import LiveOrder, TrafficState, WeatherState
from edge_server.routing.routing_engine import RoutingEngine


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


def test_orders_without_a_live_registered_driver_are_rejected_without_a_pending_record():
    with TestClient(create_app()) as client:
        customer = _account(client, name="Mariana", email="mariana@example.com", role="client")
        with client.websocket_connect("/ws") as customer_socket:
            _ready(customer_socket)
            _register_socket(customer_socket, customer)
            _new_order(customer_socket, customer)

            unavailable = _receive_until(customer_socket, "NO_DRIVERS_AVAILABLE")["data"]

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


def test_courier_requires_a_starting_pin_before_the_server_marks_it_online():
    with TestClient(create_app()) as client:
        courier = _account(client, name="Pin Required", email="pin@example.com", role="driver")
        with client.websocket_connect("/ws") as socket:
            _ready(socket)
            socket.send_json({"type": "DRIVER_ONLINE", "data": {
                "user_id": courier["user"]["id"], "session_token": courier["session_token"], "location": None,
            }})
            error = _receive_until(socket, "error")
            assert error["data"]["message"] == "Set a Monterrey starting location before going online"

            _register_socket(socket, courier, [25.6551, -100.3781])
            online = _receive_until(socket, "DRIVER_ONLINE")["data"]["driver"]
            assert online["is_available"] is True
            assert online["position"] == [25.6551, -100.3781]


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
            trace = _receive_until(customer_socket, "AI_DISPATCH_LOG")["data"]
            dispatch = _receive_until(topo_socket, "ORDER_DISPATCHED")["data"]

            assert order["status"] == "PENDING"
            assert order["driver_id"] == topo["user"]["id"]
            assert dispatch["driver"]["id"] == topo["user"]["id"]
            assert dispatch["driver"]["name"] == "Topo"
            assert dispatch["driver"]["vehicle"] == "Bicicleta eléctrica"
            assert "rating" not in dispatch["driver"]
            assert trace["selected_driver_id"] == topo["user"]["id"]
            assert {candidate["name"] for candidate in trace["candidates"]} == {"Topo", "Luz"}
            assert any(candidate["selected"] and candidate["name"] == "Topo" for candidate in trace["candidates"])

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
            assert match["order"]["courier_route_geometry"]
            assert match["order"]["route_geometry"]


def _live_coordinator() -> LiveOrderCoordinator:
    return LiveOrderCoordinator(GeminiAgent(enabled=False), RoutingEngine("https://example.invalid", use_osrm=False))


def test_weather_and_sector_costs_change_central_dispatch_choice_and_trace():
    async def scenario():
        coordinator = _live_coordinator()
        coordinator.drivers = {
            "carlos": {
                "id": "carlos", "name": "Carlos", "online": True, "is_available": True,
                "position": [25.6500, -100.3480], "assigned_order_ids": [],
            },
            "topo": {
                "id": "topo", "name": "Topo", "online": True, "is_available": True,
                "position": [25.6500, -100.4150], "assigned_order_ids": [],
            },
        }
        coordinator.traffic = TrafficState(affected_zones=["San Pedro"], congestion_level="heavy")
        coordinator.weather = WeatherState(rain_intensity=.95)
        order = LiveOrder(
            id="RUM-0001", client_id="client", client_name="Ana", restaurant="Centrito",
            origin=[25.6500, -100.3800], destination=[25.6600, -100.3900],
            location=[25.6600, -100.3900], items=[{"id": "meal"}],
        )

        selected = await coordinator._select_driver_with_trace(order.origin, [order])

        assert selected["id"] == "topo"
        assert coordinator.dispatch_log["weather_traffic_aware"] is True
        candidates = {candidate["name"]: candidate for candidate in coordinator.dispatch_log["candidates"]}
        assert "SAN_PEDRO_CONGESTION" in candidates["Carlos"]["penalty"]
        assert "TORRENTIAL_RAIN" in candidates["Topo"]["penalty"]

    asyncio.run(scenario())


def test_torrential_rain_recalculates_eta_and_courier_progress_is_three_seconds_per_kilometre():
    async def scenario():
        coordinator = _live_coordinator()
        origin, destination = [25.6500, -100.3800], [25.6600, -100.3900]
        normal, _ = await coordinator._conditioned_route(origin, destination)
        await coordinator.recalculate("TORRENTIAL_RAIN", TrafficState(), WeatherState(rain_intensity=.95, flooding_risk=.7))
        rain, _ = await coordinator._conditioned_route(origin, destination)
        assert rain.duration_minutes == pytest.approx(normal.duration_minutes / .65, abs=.02)

        order = LiveOrder(
            id="RUM-0002", client_id="client", origin=origin, destination=destination,
            location=destination, items=[{"id": "meal"}], status="MATCHED", driver_id="topo",
            courier_distance_km=2, courier_route_geometry=[[-100.3800, 25.6500], [-100.3900, 25.6600]],
        )
        coordinator.orders[order.id] = order
        coordinator.drivers["topo"] = {
            "id": "topo", "name": "Topo", "online": True, "is_available": True,
            "position": origin, "assigned_order_ids": [order.id], "bearing": 0,
        }

        updates = await coordinator.advance(3)

        assert updates[0]["phase"] == "COURIER_TO_STORE"
        assert updates[0]["progress"] == .5

    asyncio.run(scenario())
