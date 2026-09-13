"""Central live dispatch state for authenticated Rumbo clients and couriers."""
from __future__ import annotations

import asyncio
import math
from collections.abc import Iterable
from datetime import datetime, timezone

from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.models import (
    BatchPlan,
    DriverActionRequest,
    DriverTelemetryRequest,
    LiveOrder,
    LiveOrderRequest,
    OrderCancellationRequest,
    TrafficState,
    UserRegistration,
    WeatherState,
)
from edge_server.routing.fallback_router import haversine_km
from edge_server.routing.routing_engine import RoutingEngine

TIME_WARP = 120
MAX_DELIVERY_RADIUS_KM = 20.0
BASE_COURIER_PAYOUT_MXN = 35.0
COURIER_PAYOUT_PER_KM = 7.25
BATCH_COURIER_BONUS_RATE = .12


class NoDriversAvailableError(ValueError):
    """Raised before an order is created when no live courier has a position."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bearing(start: list[float], end: list[float]) -> float:
    """Geographic heading used by the moving vehicle icon."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*start, *end))
    delta_lon = lon2 - lon1
    x = math.sin(delta_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


class LiveOrderCoordinator:
    """Lock-protected dynamic dispatch and time-warp telemetry coordinator."""

    def __init__(self, agent: GeminiAgent, routing: RoutingEngine) -> None:
        self.agent = agent
        self.routing = routing
        self.orders: dict[str, LiveOrder] = {}
        self.users: dict[str, dict] = {}
        self.drivers: dict[str, dict] = {}
        self.telemetry: dict[str, dict] = {}
        self.batches: dict[str, BatchPlan] = {}
        self.batch: BatchPlan | None = None  # Compatibility for the original two-screen demo.
        self.dispatch_log: dict | None = None
        self._counter = 0
        self._batch_counter = 0
        self.simulation_minutes = 0.0
        self._lock = asyncio.Lock()

    def _metrics(self) -> dict:
        statuses = {status: 0 for status in ("PENDING", "MATCHED", "IN_TRANSIT", "DELIVERED", "CANCELLED")}
        for order in self.orders.values():
            statuses[order.status] = statuses.get(order.status, 0) + 1
        return {
            "online_drivers_count": sum(1 for driver in self.drivers.values() if driver["online"]),
            "orders": statuses,
            "total_orders": len(self.orders),
            "time_warp": TIME_WARP,
            "simulation_minutes": round(self.simulation_minutes, 1),
        }

    @staticmethod
    def _public_driver(driver: dict, status: str = "OFFLINE") -> dict:
        """Return only dashboard-safe profile and operational data for a courier."""
        return {
            "id": driver["id"],
            "name": driver["name"],
            "online": driver["online"],
            "is_available": bool(driver.get("is_available") and driver["online"]),
            "position": driver.get("position"),
            "bearing": driver.get("bearing", 0),
            "speed_kmh": driver.get("speed_kmh", 0),
            "street_name": driver.get("street_name"),
            "assigned_order_ids": driver.get("assigned_order_ids", []),
            "vehicle": driver.get("vehicle"),
            "avatar_url": driver.get("avatar_url"),
            "status": status,
            "updated_at": driver.get("updated_at"),
        }

    def _driver_financials(self, driver_id: str) -> dict:
        driver = self.drivers.get(driver_id)
        if not driver:
            return {"driver_id": driver_id, "current_trip_earnings_mxn": 0, "earnings_today_mxn": 0, "projected_today_mxn": 0,
                    "completed_deliveries": 0, "batch_time_saved_minutes": 0, "batch_savings_percent": 0}
        assigned = [order for order in self.orders.values() if order.driver_id == driver_id]
        completed = [order for order in assigned if order.status == "DELIVERED"]
        active = [order for order in assigned if order.status not in {"DELIVERED", "CANCELLED"}]
        driver_batches = [batch for batch in self.batches.values() if batch.driver_id == driver_id]
        time_saved = sum(max(0, batch.baseline_duration_minutes - batch.optimized_duration_minutes) for batch in driver_batches)
        savings = max((batch.savings_percent for batch in driver_batches), default=0)
        return {
            "driver_id": driver_id,
            "driver_name": driver["name"],
            "current_trip_earnings_mxn": round(sum(order.courier_payout_mxn for order in active), 2),
            "earnings_today_mxn": round(sum(order.courier_payout_mxn for order in completed), 2),
            "projected_today_mxn": round(sum(order.courier_payout_mxn for order in assigned), 2),
            "completed_deliveries": len(completed),
            "batch_time_saved_minutes": round(time_saved, 1),
            "batch_savings_percent": round(savings, 1),
        }

    def financial_snapshot(self) -> dict:
        driver_rows = [self._driver_financials(driver_id) for driver_id in self.drivers]
        return {
            "platform": {
                "platform_commission_mxn": round(sum(order.platform_commission_mxn for order in self.orders.values()), 2),
                "courier_payout_mxn": round(sum(order.courier_payout_mxn for order in self.orders.values()), 2),
                "delivery_fee_mxn": round(sum(order.delivery_fee_mxn for order in self.orders.values()), 2),
            },
            "drivers": driver_rows,
        }

    def verdict_evaluation(self) -> dict:
        batch = self.batch
        if batch is None:
            return {
                "available": False, "baseline_distance_km": 0, "optimized_distance_km": 0,
                "baseline_duration_minutes": 0, "optimized_duration_minutes": 0,
                "time_saved_minutes": 0, "fuel_savings_percent": 0,
                "courier_earning_improvement_percent": 0,
                "message": "Rumbo Edge espera pedidos cercanos para evaluar un batching real.",
            }
        time_saved = max(0, batch.baseline_duration_minutes - batch.optimized_duration_minutes)
        return {
            "available": True, "batch_id": batch.id,
            "baseline_distance_km": batch.individual_distance_km,
            "optimized_distance_km": batch.batch_distance_km,
            "baseline_duration_minutes": batch.baseline_duration_minutes,
            "optimized_duration_minutes": batch.optimized_duration_minutes,
            "time_saved_minutes": round(time_saved, 1),
            "fuel_savings_percent": batch.savings_percent,
            "courier_earning_improvement_percent": batch.courier_earning_improvement_percent,
            "message": f"✅ DECISIÓN OPTIMAL: El Batching incrementó la ganancia proyectada del courier un {batch.courier_earning_improvement_percent:.0f}% y redujo {time_saved:.1f} min de operación.",
        }

    def order_match_payload(self, order: LiveOrder) -> dict | None:
        if order.status not in {"MATCHED", "IN_TRANSIT"} or not order.driver_id or order.driver_id not in self.drivers:
            return None
        status = order.status
        return {"order": order.model_dump(mode="json"), "driver": self._public_driver(self.drivers[order.driver_id], status),
                "financials": self._driver_financials(order.driver_id)}

    def order_dispatch_payload(self, order: LiveOrder) -> dict | None:
        if order.status != "PENDING" or not order.driver_id or order.driver_id not in self.drivers:
            return None
        driver = self.drivers[order.driver_id]
        if not driver.get("online"):
            return None
        return {"order": order.model_dump(mode="json"), "driver": self._public_driver(driver, "DISPATCHED")}

    def driver_financial_update(self, driver_id: str) -> dict:
        return {"driver": self._public_driver(self.drivers[driver_id]) if driver_id in self.drivers else None,
                "financials": self._driver_financials(driver_id), "platform": self.financial_snapshot()["platform"]}

    def snapshot(self) -> dict:
        batches = [batch.model_dump(mode="json") for batch in self.batches.values()]
        return {
            "users": list(self.users.values()),
            "drivers": [self._public_driver(driver, "ONLINE") for driver in self.drivers.values() if driver.get("online")],
            "orders": [order.model_dump(mode="json") for order in self.orders.values()],
            "batches": batches,
            "batch": self.batch.model_dump(mode="json") if self.batch else None,
            "telemetry": self.telemetry,
            "metrics": self._metrics(),
            "financials": self.financial_snapshot(),
            "verdict": self.verdict_evaluation(),
            "dispatch_log": self.dispatch_log,
        }

    async def register_user(self, payload: dict) -> dict:
        request = UserRegistration.model_validate(payload)
        async with self._lock:
            user = {
                "id": request.id,
                "name": request.name,
                "email": request.email.lower(),
                "role": request.role,
                "registered_at": _utc_now(),
            }
            self.users[request.id] = user
            dispatched_order_ids: list[str] = []
            if request.role == "driver":
                current = self.drivers.get(request.id, {})
                position = request.location or current.get("position")
                self.drivers[request.id] = {
                    "id": request.id,
                    "name": request.name,
                    "online": True,
                    # A socket without a real position is online but cannot be
                    # selected as the closest courier.
                    "is_available": position is not None,
                    "position": position,
                    "bearing": current.get("bearing", 0),
                    "speed_kmh": current.get("speed_kmh", 0),
                    "street_name": current.get("street_name"),
                    "assigned_order_ids": current.get("assigned_order_ids", []),
                    "vehicle": request.vehicle,
                    "avatar_url": request.avatar_url,
                    "updated_at": _utc_now(),
                }
                # A real courier coming online may receive pending central orders.
                for batch in self.batches.values():
                    if batch.driver_id:
                        continue
                    batch_orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders and self.orders[order_id].status == "PENDING"]
                    if batch_orders:
                        await self._assign_driver(batch_orders, batch)
                        await self._attach_courier_route(batch_orders)
                        dispatched_order_ids.extend(order.id for order in batch_orders if order.driver_id)
                for order in self.orders.values():
                    if order.status == "PENDING" and not order.driver_id:
                        await self._assign_driver([order])
                        await self._attach_courier_route([order])
                        if order.driver_id:
                            dispatched_order_ids.append(order.id)
            driver = self._public_driver(self.drivers[request.id]) if request.id in self.drivers else None
            return {"user": user, "driver": driver, "metrics": self._metrics(), "dispatched_order_ids": dispatched_order_ids}

    async def create_order(self, payload: dict) -> tuple[LiveOrder, BatchPlan | None]:
        request = LiveOrderRequest.model_validate(payload)
        if haversine_km(request.origin[0], request.origin[1], request.destination[0], request.destination[1]) > MAX_DELIVERY_RADIUS_KM:
            raise ValueError("La dirección de entrega excede el límite operativo de 20 km")
        async with self._lock:
            self.dispatch_log = None
            if not self._candidate_drivers():
                raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
        estimate = await self.routing.estimate(tuple(request.origin), tuple(request.destination), TrafficState(), WeatherState())
        if estimate.distance_km > MAX_DELIVERY_RADIUS_KM:
            raise ValueError("La dirección de entrega excede el límite operativo de 20 km")
        async with self._lock:
            self.dispatch_log = None
            if not self._candidate_drivers():
                raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
            self._counter += 1
            order = LiveOrder(
                id=f"RUM-{self._counter:04d}", client_id=request.client_id, client_name=request.client_name,
                restaurant=request.restaurant, origin=request.origin, destination=request.destination,
                destination_label=request.destination_label, location=request.destination, items=request.items,
                distance_km=round(estimate.distance_km, 2), eta_minutes=round(estimate.duration_minutes, 1),
                delivery_fee_mxn=round(39 + estimate.distance_km * 8.5, 2),
                courier_payout_mxn=round(BASE_COURIER_PAYOUT_MXN + estimate.distance_km * COURIER_PAYOUT_PER_KM, 2),
                platform_commission_mxn=round(max(0, 39 + estimate.distance_km * 8.5 - (BASE_COURIER_PAYOUT_MXN + estimate.distance_km * COURIER_PAYOUT_PER_KM)), 2), route_geometry=estimate.geometry,
                street_names=estimate.street_names,
            )
            self.orders[order.id] = order
            partner = self._find_batch_partner(order)
            if partner:
                if not self._candidate_drivers([partner, order]):
                    self.orders.pop(order.id, None)
                    raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
                batch = await self._build_batch((partner, order))
                baseline_payout = partner.courier_payout_mxn + order.courier_payout_mxn
                optimized_payout = round(baseline_payout * (1 + BATCH_COURIER_BONUS_RATE), 2)
                total_distance = max(partner.distance_km + order.distance_km, .01)
                for candidate in (partner, order):
                    candidate.courier_payout_mxn = round(optimized_payout * candidate.distance_km / total_distance, 2)
                    candidate.platform_commission_mxn = round(max(0, candidate.delivery_fee_mxn - candidate.courier_payout_mxn), 2)
                self.batches[batch.id] = batch
                self.batch = batch
                await self._assign_driver([partner, order], batch)
                await self._attach_courier_route([partner, order])
                return order, batch
            if not self._candidate_drivers([order]):
                self.orders.pop(order.id, None)
                raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
            await self._assign_driver([order])
            await self._attach_courier_route([order])
            return order, None

    def _find_batch_partner(self, incoming: LiveOrder) -> LiveOrder | None:
        candidates = [
            order for order in self.orders.values()
            if order.id != incoming.id and order.status == "PENDING" and not order.batch_id
            and haversine_km(order.origin[0], order.origin[1], incoming.origin[0], incoming.origin[1]) <= 3.0
            and haversine_km(order.destination[0], order.destination[1], incoming.destination[0], incoming.destination[1]) <= 12.0
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda order: haversine_km(order.destination[0], order.destination[1], incoming.destination[0], incoming.destination[1]))

    def _candidate_drivers(self, orders: Iterable[LiveOrder] = ()) -> list[dict]:
        order_ids = {order.id for order in orders}
        return [
            driver for driver in self.drivers.values()
            if driver.get("online") and driver.get("is_available") and driver.get("position") is not None
            and len(driver["assigned_order_ids"]) + len(order_ids - set(driver["assigned_order_ids"])) <= 2
        ]

    async def _select_driver_with_trace(self, origin: list[float], orders: list[LiveOrder]) -> dict | None:
        """Evaluate each live courier with the same OSRM street graph used by navigation."""
        candidates = self._candidate_drivers(orders)
        if not candidates:
            return None
        evaluations: list[tuple[dict, float, float]] = []
        for driver in candidates:
            estimate = await self.routing.estimate(tuple(driver["position"]), tuple(origin), TrafficState(), WeatherState())
            evaluations.append((driver, round(estimate.distance_km, 2), round(estimate.duration_minutes, 1)))
        selected, selected_distance, selected_eta = min(
            evaluations,
            key=lambda value: (value[2], value[1], len(value[0]["assigned_order_ids"]), value[0]["id"]),
        )
        if len(evaluations) >= 2:
            slowest_eta = max(eta for _, _, eta in evaluations)
            saved_minutes = max(0, round(slowest_eta - selected_eta, 1))
            self.dispatch_log = {
                "order_ids": [order.id for order in orders],
                "selected_driver_id": selected["id"],
                "candidates": [
                    {
                        "driver_id": driver["id"], "name": driver["name"],
                        "distance_km": distance, "eta_minutes": eta,
                        "selected": driver["id"] == selected["id"],
                    }
                    for driver, distance, eta in evaluations
                ],
                "reason": (
                    f"{selected['name']} reduces restaurant arrival by {saved_minutes:.1f} min "
                    "and minimizes the delivery route footprint."
                ),
                "selected_distance_km": selected_distance,
                "selected_eta_minutes": selected_eta,
                "created_at": _utc_now(),
            }
        return selected

    async def _assign_driver(self, orders: list[LiveOrder], batch: BatchPlan | None = None) -> dict | None:
        driver = await self._select_driver_with_trace(orders[0].origin, orders)
        if driver is None:
            return None
        for order in orders:
            previous_driver = self.drivers.get(order.driver_id or "")
            if previous_driver and previous_driver["id"] != driver["id"]:
                previous_driver["assigned_order_ids"] = [assigned_id for assigned_id in previous_driver["assigned_order_ids"] if assigned_id != order.id]
                previous_driver["updated_at"] = _utc_now()
            # Dispatch is a reservation only. The courier must accept before this
            # order becomes MATCHED and visible to the customer as assigned.
            order.status = "PENDING"
            order.driver_id = driver["id"]
            order.batch_id = batch.id if batch else None
            if order.id not in driver["assigned_order_ids"]:
                driver["assigned_order_ids"].append(order.id)
            driver.pop(f"_approach_{order.id}", None)
            driver.pop(f"_progress_{order.id}", None)
        driver["updated_at"] = _utc_now()
        if batch:
            batch.driver_id = driver["id"]
        return driver

    async def _attach_courier_route(self, orders: list[LiveOrder]) -> None:
        """Attach the third, street-level leg: assigned courier to restaurant."""
        if not orders or not orders[0].driver_id:
            return
        driver = self.drivers.get(orders[0].driver_id)
        if not driver or not driver.get("position"):
            return
        estimate = await self.routing.estimate(
            tuple(driver["position"]), tuple(orders[0].origin), TrafficState(), WeatherState(),
        )
        for order in orders:
            order.courier_route_geometry = estimate.geometry
            order.courier_distance_km = round(estimate.distance_km, 2)
            order.courier_eta_minutes = round(estimate.duration_minutes, 1)
            order.courier_street_names = estimate.street_names

    async def _build_batch(self, orders: Iterable[LiveOrder]) -> BatchPlan:
        first, second = sorted(orders, key=lambda order: order.distance_km)
        pickup = first.origin
        leg_one = await self.routing.estimate(tuple(pickup), tuple(first.destination), TrafficState(), WeatherState())
        leg_two = await self.routing.estimate(tuple(first.destination), tuple(second.destination), TrafficState(), WeatherState())
        geometry = list(leg_one.geometry)
        if leg_two.geometry:
            geometry.extend(leg_two.geometry[1:] if geometry else leg_two.geometry)
        # Every client attached to this batch receives the shared route geometry.
        # The UI can therefore render the courier on the same polyline it sees in the HUD.
        for order in (first, second):
            order.route_geometry = geometry
            order.street_names = list(dict.fromkeys([*leg_one.street_names, *leg_two.street_names]))
        individual_distance = first.distance_km + second.distance_km
        batch_distance = leg_one.distance_km + leg_two.distance_km
        savings = max(0.0, (individual_distance - batch_distance) / max(individual_distance, 0.001) * 100)
        self._batch_counter += 1
        reasoning = await self._strategic_reasoning(first, second, savings)
        return BatchPlan(
            id=f"BATCH-LIVE-{self._batch_counter:03d}", order_ids=[first.id, second.id],
            client_ids=[first.client_id, second.client_id], pickup=pickup,
            route=[[pickup[0], pickup[1]], *[[lat, lon] for lon, lat in geometry]],
            individual_distance_km=round(individual_distance, 2), batch_distance_km=round(batch_distance, 2),
            savings_percent=round(savings, 1), reasoning=reasoning,
            baseline_duration_minutes=round(first.eta_minutes + second.eta_minutes, 1),
            optimized_duration_minutes=round(leg_one.duration_minutes + leg_two.duration_minutes, 1),
            courier_earning_improvement_percent=round(BATCH_COURIER_BONUS_RATE * 100, 1),
        )

    async def _strategic_reasoning(self, first: LiveOrder, second: LiveOrder, savings: float) -> str:
        return (
            f"Rumbo Edge grouped the real nearby destinations for {first.client_name} and "
            f"{second.client_name}. Calculated distance saving: {savings:.1f}%"
        )

    async def apply_driver_action(self, payload: dict) -> tuple[BatchPlan | None, list[LiveOrder]]:
        request = DriverActionRequest.model_validate(payload)
        async with self._lock:
            batch = self.batches.get(request.batch_id or "")
            orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders] if batch else []
            if request.order_id and request.order_id in self.orders:
                orders = [self.orders[request.order_id]]
                batch = self.batches.get(orders[0].batch_id or "")
            elif not batch and self.batch and not request.order_id:
                batch = self.batch
                orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders]
            driver_id = request.driver_id or (batch.driver_id if batch else None) or (orders[0].driver_id if orders else None)
            if not orders:
                return batch, []
            if not driver_id or any(order.driver_id != driver_id for order in orders):
                raise ValueError("This courier is not assigned to the selected order")
            if request.action in {"ACCEPT_BATCH", "ACCEPT_ASSIGNMENT"}:
                for order in orders:
                    order.status = "MATCHED"
                if batch:
                    batch.status = "ACCEPTED"
                # Re-evaluate courier → restaurant after acceptance, using the
                # courier's latest central position before animation begins.
                await self._attach_courier_route(orders)
            elif request.action == "START_DELIVERY":
                for order in orders:
                    order.status = "IN_TRANSIT"
                if batch:
                    batch.status = "IN_TRANSIT"
            elif request.action == "ARRIVED_RESTAURANT":
                if batch:
                    batch.status = "AT_RESTAURANT"
            else:
                target_id = request.order_id
                if request.action.startswith("DELIVERED_CLIENT_"):
                    legacy_client = request.action.replace("DELIVERED_", "").lower()
                    target_id = next((order.id for order in orders if order.client_id == legacy_client), None)
                targets = [self.orders[target_id]] if target_id and target_id in self.orders else orders
                for order in targets:
                    order.status = "DELIVERED"
                if batch and all(order.status == "DELIVERED" for order in orders):
                    batch.status = "COMPLETED"
            self._release_finished_driver(driver_id)
            return batch, orders

    async def set_driver_online(self, driver_id: str, online: bool) -> dict | None:
        """Socket presence is the only source of a courier's availability state."""
        async with self._lock:
            driver = self.drivers.get(driver_id)
            if not driver:
                return None
            driver["online"] = online
            driver["is_available"] = bool(online and driver.get("position") is not None)
            driver["updated_at"] = _utc_now()
            if not online:
                self.telemetry.pop(driver_id, None)
                # A dispatch is only a reservation until the courier accepts it.
                # Once its real socket closes, return those pending orders to the
                # central queue instead of leaving them tied to a ghost courier.
                released_ids = {
                    order.id for order in self.orders.values()
                    if order.driver_id == driver_id and order.status == "PENDING"
                }
                for order_id in released_ids:
                    order = self.orders[order_id]
                    order.driver_id = None
                    order.courier_route_geometry = []
                    order.courier_distance_km = None
                    order.courier_eta_minutes = None
                    order.courier_street_names = []
                for batch in self.batches.values():
                    if batch.driver_id == driver_id and any(order_id in released_ids for order_id in batch.order_ids):
                        batch.driver_id = None
                driver["assigned_order_ids"] = [
                    order_id for order_id in driver["assigned_order_ids"] if order_id not in released_ids
                ]
            return self._public_driver(driver, "ONLINE" if online else "OFFLINE")

    async def redispatch_pending_orders(self) -> list[LiveOrder]:
        """Assign queue entries only to couriers whose authenticated sockets remain live."""
        async with self._lock:
            dispatched: list[LiveOrder] = []
            processed: set[str] = set()
            for batch in self.batches.values():
                batch_orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders]
                if not batch_orders or batch.driver_id or any(order.status != "PENDING" or order.driver_id for order in batch_orders):
                    continue
                await self._assign_driver(batch_orders, batch)
                if batch.driver_id:
                    await self._attach_courier_route(batch_orders)
                    dispatched.extend(batch_orders)
                    processed.update(order.id for order in batch_orders)
            for order in self.orders.values():
                if order.id in processed or order.status != "PENDING" or order.driver_id or order.batch_id:
                    continue
                await self._assign_driver([order])
                if order.driver_id:
                    await self._attach_courier_route([order])
                    dispatched.append(order)
            return dispatched

    def _release_finished_driver(self, driver_id: str | None) -> None:
        if not driver_id or driver_id not in self.drivers:
            return
        driver = self.drivers[driver_id]
        driver["assigned_order_ids"] = [
            order_id for order_id in driver["assigned_order_ids"]
            if self.orders.get(order_id) and self.orders[order_id].status not in {"DELIVERED", "CANCELLED"}
        ]
        driver["updated_at"] = _utc_now()

    async def cancel_order(self, payload: dict) -> tuple[LiveOrder, BatchPlan | None]:
        """Cancel an undelivered order and immediately free it from its courier HUD."""
        request = OrderCancellationRequest.model_validate(payload)
        async with self._lock:
            order = self.orders.get(request.order_id)
            if not order or order.client_id != request.client_id:
                raise ValueError("Order was not found for this client")
            if order.status in {"DELIVERED", "CANCELLED"}:
                raise ValueError("Only an active order can be cancelled")

            driver_id = order.driver_id
            batch = self.batches.get(order.batch_id or "")
            order.status = "CANCELLED"
            self._release_finished_driver(driver_id)

            if batch:
                remaining = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders and self.orders[order_id].status != "CANCELLED"]
                batch.status = "PARTIALLY_CANCELLED" if remaining else "CANCELLED"
                if remaining:
                    # A partial batch becomes a normal direct delivery. Its original
                    # shared geometry must not route the courier through a cancelled stop.
                    for remaining_order in remaining:
                        remaining_order.batch_id = None
                        direct = await self.routing.estimate(
                            tuple(remaining_order.origin), tuple(remaining_order.destination), TrafficState(), WeatherState(),
                        )
                        remaining_order.route_geometry = direct.geometry
                        remaining_order.street_names = direct.street_names
                        remaining_order.distance_km = round(direct.distance_km, 2)
                        remaining_order.eta_minutes = round(direct.duration_minutes, 1)
                    await self._attach_courier_route(remaining)
                if self.batch and self.batch.id == batch.id:
                    self.batch = None
            return order, batch

    async def update_telemetry(self, payload: dict) -> dict:
        request = DriverTelemetryRequest.model_validate(payload)
        async with self._lock:
            driver = self.drivers.get(request.driver_id)
            if not driver:
                raise ValueError("Register the courier before sending telemetry")
            driver.update({"position": request.position, "bearing": request.bearing, "street_name": request.street_name,
                           "speed_kmh": request.speed_kmh, "updated_at": _utc_now()})
            driver["is_available"] = bool(driver.get("online"))
            telemetry = {"driver_id": request.driver_id, "position": request.position, "bearing": request.bearing,
                         "street_name": request.street_name, "speed_kmh": request.speed_kmh, "timestamp": _utc_now()}
            self.telemetry[request.driver_id] = telemetry
            return telemetry

    async def advance(self, real_seconds: float = 0.5) -> list[dict]:
        """Advance server-side courier snapshots; browsers interpolate them at 60 FPS."""
        async with self._lock:
            self.simulation_minutes += real_seconds * TIME_WARP / 60
            updates: list[dict] = []
            for driver_id, driver in self.drivers.items():
                if not driver.get("online"):
                    continue
                active_orders = [
                    self.orders[order_id] for order_id in driver["assigned_order_ids"]
                    if order_id in self.orders and self.orders[order_id].status in {"MATCHED", "IN_TRANSIT"}
                ]
                if not active_orders:
                    continue
                active = active_orders[0]
                batch = self.batches.get(active.batch_id or "")
                batch_orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders] if batch else []
                if active.status == "MATCHED":
                    # Phase one: the courier follows the server-calculated OSRM
                    # approach route to the restaurant before delivery begins.
                    geometry = active.courier_route_geometry
                    if len(geometry) < 2:
                        continue
                    route_minutes = max(active.courier_eta_minutes, 1)
                    key = f"_approach_{batch.id if batch else active.id}"
                    progress = min(1.0, driver.get(key, 0.0) + (real_seconds * TIME_WARP / 60) / route_minutes)
                    driver[key] = progress
                    segment_progress = progress * (len(geometry) - 1)
                    index = min(len(geometry) - 1, int(segment_progress))
                    next_index = min(index + 1, len(geometry) - 1)
                    fraction = segment_progress - index
                    lon, lat = geometry[index]
                    next_lon, next_lat = geometry[next_index]
                    position = [lat + (next_lat - lat) * fraction, lon + (next_lon - lon) * fraction]
                    bearing = _bearing(position, [next_lat, next_lon]) if index < len(geometry) - 1 else driver.get("bearing", 0)
                    street_names = active.courier_street_names
                    street_index = min(len(street_names) - 1, int(progress * len(street_names))) if street_names else 0
                    telemetry = {
                        "driver_id": driver_id, "position": position, "bearing": round(bearing, 1),
                        "street_name": street_names[street_index] if street_names else "",
                        "speed_kmh": 45, "order_id": active.id, "phase": "COURIER_TO_STORE",
                        "progress": round(progress, 4), "timestamp": _utc_now(),
                    }
                    driver.update(telemetry)
                    self.telemetry[driver_id] = telemetry
                    updates.append(telemetry)
                    if progress >= 1:
                        if batch and len(batch_orders) > 1:
                            for order in batch_orders:
                                if order.status == "MATCHED":
                                    order.status = "IN_TRANSIT"
                            batch.status = "IN_TRANSIT"
                        else:
                            active.status = "IN_TRANSIT"
                    continue
                # A batch follows one continuous street geometry. The second destination
                # therefore starts where the first delivery ends, never teleports back to
                # a restaurant-specific route.
                if batch and len(batch_orders) > 1:
                    geometry = [[lon, lat] for lat, lon in batch.route]
                    route_minutes = max(sum(order.eta_minutes for order in batch_orders), 1)
                    key = f"_progress_{batch.id}"
                    street_names = [name for order in batch_orders for name in order.street_names]
                else:
                    geometry = active.route_geometry or [[active.origin[1], active.origin[0]], [active.destination[1], active.destination[0]]]
                    route_minutes = max(active.eta_minutes, 1)
                    key = f"_progress_{active.id}"
                    street_names = active.street_names
                progress = min(1.0, driver.get(key, 0.0) + (real_seconds * TIME_WARP / 60) / route_minutes)
                driver[key] = progress
                segment_progress = progress * max(len(geometry) - 1, 1)
                index = min(len(geometry) - 1, int(segment_progress))
                next_index = min(index + 1, len(geometry) - 1)
                segment_fraction = segment_progress - index
                lon, lat = geometry[index]
                next_lon, next_lat = geometry[next_index]
                # This is intentionally an interpolation on the OSRM geometry itself,
                # not a straight-line shortcut between destinations.
                lon = lon + (next_lon - lon) * segment_fraction
                lat = lat + (next_lat - lat) * segment_fraction
                position = [lat, lon]
                bearing = _bearing(position, [next_lat, next_lon]) if index < len(geometry) - 1 else driver.get("bearing", 0)
                street_index = min(len(street_names) - 1, int(progress * len(street_names))) if street_names else 0
                telemetry = {
                    "driver_id": driver_id, "position": position, "bearing": round(bearing, 1),
                    "street_name": street_names[street_index] if street_names else "",
                    "speed_kmh": 45, "order_id": active.id, "phase": "STORE_TO_CLIENT",
                    "progress": round(progress, 4), "timestamp": _utc_now(),
                }
                driver.update(telemetry)
                self.telemetry[driver_id] = telemetry
                updates.append(telemetry)
                if batch and len(batch_orders) > 1:
                    first_stop_progress = min(.92, max(.08, batch_orders[0].distance_km / max(batch.batch_distance_km, .01)))
                    if progress >= first_stop_progress and batch_orders[0].status == "IN_TRANSIT":
                        batch_orders[0].status = "DELIVERED"
                    if progress >= 1:
                        for order in batch_orders:
                            order.status = "DELIVERED"
                        batch.status = "COMPLETED"
                        self._release_finished_driver(driver_id)
                elif progress >= 1:
                    active.status = "DELIVERED"
                    self._release_finished_driver(driver_id)
            return updates

    async def recalculate(self, disruption: str, traffic: TrafficState | None = None, weather: WeatherState | None = None) -> BatchPlan | None:
        async with self._lock:
            if not self.batch:
                return None
            traffic, weather = traffic or TrafficState(), weather or WeatherState()
            orders = [self.orders[order_id] for order_id in self.batch.order_ids if order_id in self.orders]
            if len(orders) == 2:
                # Re-query road geometry under the new network conditions. The route's
                # geometry, ETA and savings are all refreshed rather than only its copy.
                first, second = sorted(orders, key=lambda order: order.distance_km)
                for order in orders:
                    direct = await self.routing.estimate(tuple(order.origin), tuple(order.destination), traffic, weather)
                    order.distance_km = round(direct.distance_km, 2)
                    order.eta_minutes = round(direct.duration_minutes, 1)
                    order.route_geometry = direct.geometry
                    order.street_names = direct.street_names
                    order.delivery_fee_mxn = round(39 + direct.distance_km * 8.5, 2)
                leg_one = await self.routing.estimate(tuple(first.origin), tuple(first.destination), traffic, weather)
                leg_two = await self.routing.estimate(tuple(first.destination), tuple(second.destination), traffic, weather)
                geometry = list(leg_one.geometry)
                if leg_two.geometry:
                    geometry.extend(leg_two.geometry[1:] if geometry else leg_two.geometry)
                for order in orders:
                    order.route_geometry = geometry
                    order.street_names = list(dict.fromkeys([*leg_one.street_names, *leg_two.street_names]))
                self.batch.route = [[first.origin[0], first.origin[1]], *[[lat, lon] for lon, lat in geometry]]
                self.batch.individual_distance_km = round(sum(order.distance_km for order in orders), 2)
                self.batch.batch_distance_km = round(leg_one.distance_km + leg_two.distance_km, 2)
                self.batch.baseline_duration_minutes = round(sum(order.eta_minutes for order in orders), 1)
                self.batch.optimized_duration_minutes = round(leg_one.duration_minutes + leg_two.duration_minutes, 1)
                self.batch.savings_percent = round(max(0.0, (self.batch.individual_distance_km - self.batch.batch_distance_km) / max(self.batch.individual_distance_km, .001) * 100), 1)
            impacts = {
                "TORRENTIAL_RAIN": "Lluvia torrencial: Rumbo recalculó la ruta y preservó el batch con prioridad de seguridad.",
                "GONZALITOS_FLOOD": "Inundación en Gonzalitos: Rumbo evitó la zona afectada y recalculó la secuencia de entrega.",
                "SAN_PEDRO_CONGESTION": "Congestionamiento en San Pedro: Rumbo recalculó ETA y mantuvo la ruta de menor costo.",
            }
            self.batch.reasoning = f"{impacts.get(disruption, 'Rumbo Edge actualizó la recomendación con el nuevo estado vial.')} Ruta y ETA recalculados; {self.batch.savings_percent:.1f}% de ahorro calculado."
            self.batch.status = f"RECALCULATED_{disruption}"
            return self.batch
