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
MOTION_SECONDS_PER_KM = 3.0
BASE_COURIER_PAYOUT_MXN = 35.0
COURIER_PAYOUT_PER_KM = 7.25
BATCH_COURIER_BONUS_RATE = .12
CONGESTION_ZONES = {
    "San Pedro": ([25.6500, -100.3500], 2.7, 2.2),
    "Gonzalitos": ([25.6900, -100.3660], 2.4, 2.3),
}
FLAGGED_ZONE_BOUNDS = {
    99: (25.6778, 25.6850, -100.3290, -100.3150),
    13: (25.7390, 25.7490, -100.3600, -100.3420),
    15: (25.6350, 25.6430, -100.2940, -100.2780),
    22: (25.8060, 25.8180, -100.3320, -100.3120),
    31: (25.5990, 25.6090, -100.1940, -100.1740),
}
VEHICLE_CAPACITY = {
    "moto": (20.0, 20.0),
    "car": (150.0, 200.0),
    "bike": (8.0, 12.0),
}
VEHICLE_SECONDS_PER_KM = {"moto": 3.0, "car": 3.9, "bike": 7.5}
VEHICLE_DISPLAY_SPEED_KMH = {"moto": 45, "car": 35, "bike": 18}


def _flagged_zone_id(position: list[float]) -> int | None:
    lat, lon = position
    for zone_id, (min_lat, max_lat, min_lon, max_lon) in FLAGGED_ZONE_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return zone_id
    return None


def _minutes_in_day(value: float) -> float:
    return value % (24 * 60)


def _point_on_geometry(geometry: list[list[float]], progress: float) -> tuple[list[float], float]:
    """Interpolate by travelled street distance, never by polyline point count."""
    if len(geometry) < 2:
        point = geometry[0] if geometry else [-100.3161, 25.6866]
        return [point[1], point[0]], 0.0
    distances = [
        haversine_km(start[1], start[0], end[1], end[0])
        for start, end in zip(geometry, geometry[1:])
    ]
    total = max(sum(distances), 0.000_001)
    remaining = min(1.0, max(0.0, progress)) * total
    for index, distance in enumerate(distances):
        if remaining <= distance or index == len(distances) - 1:
            fraction = remaining / max(distance, 0.000_001)
            lon, lat = geometry[index]
            next_lon, next_lat = geometry[index + 1]
            position = [lat + (next_lat - lat) * fraction, lon + (next_lon - lon) * fraction]
            return position, _bearing(position, [next_lat, next_lon])
        remaining -= distance
    last = geometry[-1]
    previous = geometry[-2]
    return [last[1], last[0]], _bearing([previous[1], previous[0]], [last[1], last[0]])


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
        self.dispatch_history: list[dict] = []
        self.traffic_impact: dict = {"minutes": 0.0, "message": "Normal traffic conditions."}
        self._counter = 0
        self._batch_counter = 0
        self.simulation_minutes = 14 * 60.0
        self.traffic = TrafficState()
        self.weather = WeatherState()
        self.road_closures: list[dict] = []
        self.surge_multiplier = 1.0
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
            "status": driver.get("status", status),
            "shift_start_minute": driver.get("shift_start_minute"),
            "shift_end_minute": driver.get("shift_end_minute"),
            "continuous_riding_minutes": round(driver.get("continuous_riding_minutes", 0), 1),
            "break_until_minute": driver.get("break_until_minute"),
            "delay_until_minute": driver.get("delay_until_minute"),
            "heat_rule_alert": bool(driver.get("heat_rule_alert")),
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

    def _remember_decision(self, decision: dict) -> None:
        """Retain an additive, serializable audit history for the judge UI."""
        key = decision.get("id") or f"decision-{len(self.dispatch_history) + 1}"
        decision["id"] = key
        self.dispatch_log = decision
        self.dispatch_history = [item for item in self.dispatch_history if item.get("id") != key]
        self.dispatch_history.insert(0, decision)
        self.dispatch_history = self.dispatch_history[:80]

    def _record_safety_decision(self, *, order_id: str, tag: str, reason: str, origin: list[float] | None = None, destination: list[float] | None = None) -> None:
        self._remember_decision({
            "id": f"safety-{order_id}-{tag.lower().replace(' ', '-')}", "order_ids": [order_id],
            "selected_driver_id": None, "candidates": [], "reason": reason, "tags": [tag],
            "origin": origin, "destination": destination, "created_at": _utc_now(),
        })

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
            "dispatch_history": self.dispatch_history,
            "traffic_impact": self.traffic_impact,
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
                requested_start = payload.get("shift_start_minute")
                shift_start = float(_minutes_in_day(self.simulation_minutes) if requested_start is None else requested_start)
                requested_end = payload.get("shift_end_minute")
                shift_end = float(shift_start + 240 if requested_end is None else requested_end)
                if not shift_start < shift_end <= 24 * 60 or shift_end - shift_start > 240:
                    raise ValueError("Courier shifts must be between 1 minute and 4 hours within the same day")
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
                    "vehicle_profile": payload.get("vehicle_profile", current.get("vehicle_profile")),
                    "avatar_url": request.avatar_url,
                    "shift_start_minute": shift_start,
                    "shift_end_minute": shift_end,
                    "continuous_riding_minutes": current.get("continuous_riding_minutes", 0.0),
                    "break_until_minute": current.get("break_until_minute"),
                    "delay_until_minute": current.get("delay_until_minute"),
                    "heat_rule_alert": False,
                    "status": "ONLINE",
                    "updated_at": _utc_now(),
                }
                self._refresh_driver_status(self.drivers[request.id])
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
        if _minutes_in_day(self.simulation_minutes) >= 22 * 60 and _flagged_zone_id(request.destination):
            self._record_safety_decision(
                order_id=f"request-{self._counter + 1}", tag="FLAGGED ZONE PREVENTED",
                reason="Flagged Zone prevented: delivery selection is unavailable after 22:00.",
                origin=request.origin, destination=request.destination,
            )
            raise ValueError("🚫 Flagged Zone unavailable after 22:00")
        async with self._lock:
            if not self._candidate_drivers():
                active_drivers = [driver for driver in self.drivers.values() if driver.get("online")]
                tag = "HEAT RULE BLOCKED" if any(driver.get("status") == "ON_BREAK" for driver in active_drivers) else "VEHICLE CAPACITY BLOCKED"
                self._record_safety_decision(
                    order_id=f"request-{self._counter + 1}", tag=tag,
                    reason="No eligible courier can safely accept this order under the current Pi dispatch constraints.",
                    origin=request.origin, destination=request.destination,
                )
                raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
        estimate, _ = await self._conditioned_route(request.origin, request.destination)
        if estimate.distance_km > MAX_DELIVERY_RADIUS_KM:
            raise ValueError("La dirección de entrega excede el límite operativo de 20 km")
        async with self._lock:
            if not self._candidate_drivers():
                self._record_safety_decision(
                    order_id=f"request-{self._counter + 1}", tag="VEHICLE CAPACITY BLOCKED",
                    reason="No eligible courier remains after central capacity and availability validation.",
                    origin=request.origin, destination=request.destination,
                )
                raise NoDriversAvailableError("No hay repartidores disponibles en este momento")
            self._counter += 1
            order = LiveOrder(
                id=f"RUM-{self._counter:04d}", client_id=request.client_id, client_name=request.client_name,
                restaurant=request.restaurant, origin=request.origin, destination=request.destination,
                destination_label=request.destination_label, location=request.destination, items=request.items,
                distance_km=round(estimate.distance_km, 2), eta_minutes=round(estimate.duration_minutes, 1),
                delivery_fee_mxn=round(39 + estimate.distance_km * 8.5, 2),
                courier_payout_mxn=round(BASE_COURIER_PAYOUT_MXN + estimate.distance_km * COURIER_PAYOUT_PER_KM + request.tip_mxn, 2),
                platform_commission_mxn=round(max(0, 39 + estimate.distance_km * 8.5 - (BASE_COURIER_PAYOUT_MXN + estimate.distance_km * COURIER_PAYOUT_PER_KM)), 2),
                tip_mxn=request.tip_mxn, weight_kg=request.weight_kg or 1.0, volume_liters=request.volume_liters or 1.0, route_geometry=estimate.geometry,
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

    def _route_penalties(self, estimate, origin: list[float], destination: list[float]) -> tuple[float, list[str]]:
        """Apply local disruption cost only where an OSRM path enters its sector."""
        factor = 1.0
        notes: list[str] = []
        if self.weather.rain_intensity >= .8:
            notes.append("TORRENTIAL_RAIN (-35% speed)")
        points = [[lat, lon] for lon, lat in estimate.geometry] or [origin, destination]
        for zone in self.traffic.affected_zones:
            config = CONGESTION_ZONES.get(zone)
            if not config:
                continue
            center, radius_km, zone_factor = config
            # OSRM geometries contain the actual street shape. The fallback only
            # contains endpoints, so sample each segment as well: a corridor that
            # crosses a disruption is penalised even if neither endpoint is in it.
            sampled = list(points)
            for start, end in zip(points, points[1:]):
                steps = max(1, math.ceil(haversine_km(start[0], start[1], end[0], end[1]) / .2))
                sampled.extend([
                    [start[0] + (end[0] - start[0]) * step / steps, start[1] + (end[1] - start[1]) * step / steps]
                    for step in range(1, steps)
                ])
            if any(haversine_km(point[0], point[1], center[0], center[1]) <= radius_km for point in sampled):
                factor = max(factor, zone_factor)
                disruption_name = {
                    "San Pedro": "SAN_PEDRO_CONGESTION",
                    "Gonzalitos": "GONZALITOS_FLOOD",
                }.get(zone, zone.upper().replace(" ", "_"))
                notes.append(f"{disruption_name} (x{zone_factor:.1f})")
        for closure in self.road_closures:
            position = closure.get("position")
            if not position or len(position) != 2:
                continue
            if any(haversine_km(point[0], point[1], position[0], position[1]) <= .7 for point in points):
                factor = max(factor, 3.0)
                notes.append(f"ROAD_CLOSURE ({closure.get('label', 'pinned')})")
        return factor, notes

    async def _conditioned_route(self, origin: list[float], destination: list[float]):
        estimate = await self.routing.estimate(tuple(origin), tuple(destination), self.traffic, self.weather)
        factor, notes = self._route_penalties(estimate, origin, destination)
        estimate.duration_minutes = round(estimate.duration_minutes * factor, 2)
        return estimate, notes

    @staticmethod
    def _vehicle_key(vehicle: str | None) -> str:
        normalized = (vehicle or "moto").strip().lower()
        if any(token in normalized for token in ("bike", "bici", "bicic")):
            return "bike"
        if any(token in normalized for token in ("car", "auto", "coche")):
            return "car"
        return "moto"

    def _fits_capacity(self, driver: dict, order: LiveOrder) -> bool:
        max_weight, max_volume = VEHICLE_CAPACITY[self._vehicle_key(driver.get("vehicle_profile") or driver.get("vehicle"))]
        return order.weight_kg <= max_weight and order.volume_liters <= max_volume

    def _refresh_driver_status(self, driver: dict) -> None:
        """Apply only live-operation availability rules; evaluation state is separate."""
        now = _minutes_in_day(self.simulation_minutes)
        start = driver.get("shift_start_minute")
        end = driver.get("shift_end_minute")
        if start is not None and end is not None and not (start <= now <= end):
            driver["is_available"] = False
            driver["status"] = "OFF_SHIFT"
            return
        if (driver.get("delay_until_minute") or 0) > self.simulation_minutes:
            driver["is_available"] = False
            driver["status"] = "DELAYED"
            return
        if (driver.get("break_until_minute") or 0) > self.simulation_minutes:
            driver["is_available"] = False
            driver["status"] = "ON_BREAK"
            return
        if driver.get("status") in {"DELAYED", "ON_BREAK", "OFF_SHIFT"}:
            driver["status"] = "ONLINE"
            driver["delay_until_minute"] = None
            driver["break_until_minute"] = None
            driver["continuous_riding_minutes"] = 0.0
        driver["is_available"] = bool(driver.get("online") and driver.get("position") is not None)

    async def apply_control_state(self, state: dict) -> None:
        """Receive the Pi-owned Time Machine state before dispatch or motion ticks."""
        async with self._lock:
            self.simulation_minutes = float(state.get("simulated_minutes", self.simulation_minutes))
            self.road_closures = list(state.get("road_closures") or [])
            self.surge_multiplier = float(state.get("surge_multiplier", 1.0))
            for driver_id, delay in (state.get("driver_delays") or {}).items():
                driver = self.drivers.get(driver_id)
                if driver:
                    driver["delay_until_minute"] = float(delay.get("until_minute", self.simulation_minutes))
                    driver["status"] = "DELAYED"
            for driver in self.drivers.values():
                self._refresh_driver_status(driver)

    async def apply_driver_delay(self, driver_id: str, minutes: float) -> dict | None:
        async with self._lock:
            driver = self.drivers.get(driver_id)
            if not driver:
                return None
            applied_minutes = max(1.0, minutes)
            driver["delay_until_minute"] = self.simulation_minutes + applied_minutes
            driver["status"] = "DELAYED"
            driver["is_available"] = False
            driver["updated_at"] = _utc_now()
            # The customer and Command Center consume these server-owned ETAs;
            # apply the selected kitchen delay once, without creating a local UI
            # estimate or compounding it every telemetry tick.
            for order in self.orders.values():
                if order.driver_id == driver_id and order.status in {"PENDING", "MATCHED", "IN_TRANSIT"}:
                    order.eta_minutes = round(order.eta_minutes + applied_minutes, 1)
                    if order.status == "MATCHED":
                        order.courier_eta_minutes = round(order.courier_eta_minutes + applied_minutes, 1)
            return self._public_driver(driver, "DELAYED")

    def _candidate_drivers(self, orders: Iterable[LiveOrder] = ()) -> list[dict]:
        order_ids = {order.id for order in orders}
        return [
            driver for driver in self.drivers.values()
            if driver.get("online") and driver.get("is_available") and driver.get("position") is not None
            and len(driver["assigned_order_ids"]) + len(order_ids - set(driver["assigned_order_ids"])) <= 2
            and all(driver["id"] not in order.declined_driver_ids and self._fits_capacity(driver, order) for order in orders)
        ]

    async def _select_driver_with_trace(self, origin: list[float], orders: list[LiveOrder]) -> dict | None:
        """Evaluate each live courier with the same OSRM street graph used by navigation."""
        candidates = self._candidate_drivers(orders)
        if not candidates:
            return None
        evaluations: list[tuple[dict, float, float, list[str]]] = []
        for driver in candidates:
            estimate, penalties = await self._conditioned_route(driver["position"], origin)
            evaluations.append((driver, round(estimate.distance_km, 2), round(estimate.duration_minutes, 1), penalties))
        tip_value = sum(order.tip_mxn for order in orders)
        selected, selected_distance, selected_eta, _ = min(
            evaluations,
            # Nearby availability remains the primary signal; tips influence
            # the value score only after physical route cost is accounted for.
            key=lambda value: (value[2] - min(tip_value, 100) / 25, value[2], value[1], len(value[0]["assigned_order_ids"]), value[0]["id"]),
        )
        slowest_eta = max(eta for _, _, eta, _ in evaluations)
        saved_minutes = max(0, round(slowest_eta - selected_eta, 1))
        tags = ["PROFIT OPTIMIZED"]
        if tip_value >= 30:
            tags.append("TIP PRIORITIZED")
        if any(penalties for _, _, _, penalties in evaluations):
            tags.append("TRAFFIC AWARE")
        selected_vehicle = self._vehicle_key(selected.get("vehicle_profile") or selected.get("vehicle"))
        comparison = f" over {len(evaluations) - 1} alternative courier(s)" if len(evaluations) > 1 else " as the only eligible courier"
        tip_reason = f" after evaluating a ${tip_value:.0f} MXN tip" if tip_value else ""
        self._remember_decision({
            "id": f"dispatch-{'-'.join(order.id for order in orders)}-{int(self.simulation_minutes * 10)}",
            "order_ids": [order.id for order in orders], "selected_driver_id": selected["id"],
            "candidates": [
                {
                    "driver_id": driver["id"], "name": driver["name"],
                    "vehicle": self._vehicle_key(driver.get("vehicle_profile") or driver.get("vehicle")),
                    "distance_km": distance, "eta_minutes": eta,
                    "penalty": " · ".join(penalties) if penalties else "Clear corridor",
                    "selected": driver["id"] == selected["id"],
                }
                for driver, distance, eta, penalties in evaluations
            ],
            "reason": (
                f"Selected {selected['name']} ({selected_vehicle}, ETA {selected_eta:.1f} min){comparison}"
                f"{tip_reason}; the OSRM route saves {saved_minutes:.1f} min under current constraints."
            ),
            "tags": tags, "weather_traffic_aware": True, "selected_distance_km": selected_distance,
            "selected_eta_minutes": selected_eta, "origin": origin, "destination": orders[0].destination,
            "created_at": _utc_now(),
        })
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
        estimate, _ = await self._conditioned_route(driver["position"], orders[0].origin)
        for order in orders:
            order.courier_route_geometry = estimate.geometry
            order.courier_distance_km = round(estimate.distance_km, 2)
            order.courier_eta_minutes = round(estimate.duration_minutes, 1)
            order.courier_street_names = estimate.street_names

    async def _build_batch(self, orders: Iterable[LiveOrder]) -> BatchPlan:
        first, second = sorted(orders, key=lambda order: order.distance_km)
        pickup = first.origin
        leg_one, _ = await self._conditioned_route(pickup, first.destination)
        leg_two, _ = await self._conditioned_route(first.destination, second.destination)
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
            driver = self.drivers.get(driver_id)
            if request.action == "DECLINE_ASSIGNMENT":
                # Declining never destroys an order: it goes straight back to
                # the Pi-owned pool and excludes only the declining courier.
                if driver:
                    driver["assigned_order_ids"] = [order_id for order_id in driver["assigned_order_ids"] if order_id not in {order.id for order in orders}]
                    driver["updated_at"] = _utc_now()
                for order in orders:
                    if driver_id not in order.declined_driver_ids:
                        order.declined_driver_ids.append(driver_id)
                    order.driver_id = None
                    order.courier_route_geometry = []
                    order.courier_distance_km = 0
                    order.courier_eta_minutes = 0
                if batch:
                    batch.driver_id = None
                    batch.status = "PENDING_REASSIGNMENT"
                await self._assign_driver(orders, batch)
                await self._attach_courier_route(orders)
                return batch, orders
            if request.action in {"ACCEPT_BATCH", "ACCEPT_ASSIGNMENT"} and _minutes_in_day(self.simulation_minutes) >= 22 * 60:
                if any(_flagged_zone_id(order.origin) or _flagged_zone_id(order.destination) for order in orders):
                    raise ValueError("flagged_zone_night")
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

    async def launch_full_demo(self) -> dict:
        """Create the explicitly requested isolated 15-order / 7-courier demo mesh.

        These records exist only in coordinator memory and are identified with
        `demo-` ids, so they never alter SQLite accounts or ordinary sessions.
        """
        driver_specs = [
            ("Ariana", "moto", [25.6496, -100.3595]), ("Bruno", "bike", [25.6518, -100.2894]),
            ("Camila", "car", [25.6819, -100.3697]), ("Diego", "moto", [25.6786, -100.3428]),
            ("Elena", "bike", [25.6834, -100.3690]), ("Fabio", "car", [25.7254, -100.3863]),
            ("Gina", "moto", [25.6441, -100.3301]),
        ]
        destinations = [
            [25.6488, -100.3574], [25.6517, -100.2892], [25.6441, -100.3301], [25.6786, -100.3428],
            [25.6834, -100.3690], [25.7254, -100.3863], [25.6650, -100.3090], [25.6940, -100.3340],
            [25.6730, -100.3730], [25.6360, -100.3190], [25.7090, -100.3570], [25.6620, -100.2760],
            [25.6950, -100.3000], [25.6160, -100.3460], [25.7040, -100.4050],
        ]
        origins = [[25.6496, -100.3595], [25.6518, -100.2894], [25.6819, -100.3697]]
        async with self._lock:
            self.dispatch_history = []
            self.dispatch_log = None
            for collection in (self.users, self.drivers, self.telemetry):
                for key in [key for key in collection if key.startswith("demo-")]:
                    collection.pop(key, None)
            for key in [key for key in self.orders if key.startswith("DEMO-")]:
                self.orders.pop(key, None)

            for index, (name, vehicle, position) in enumerate(driver_specs, start=1):
                driver_id = f"demo-driver-{index}"
                self.users[driver_id] = {"id": driver_id, "name": name, "email": f"{driver_id}@rumbo.demo", "role": "driver", "registered_at": _utc_now()}
                self.drivers[driver_id] = {
                    "id": driver_id, "name": name, "online": True, "is_available": True, "position": position,
                    "bearing": 0, "speed_kmh": 0, "street_name": "Monterrey", "assigned_order_ids": [],
                    "vehicle": {"moto": "Moto demo", "bike": "Bicicleta demo", "car": "Auto demo"}[vehicle],
                    "vehicle_profile": vehicle, "avatar_url": None, "shift_start_minute": 14 * 60,
                    "shift_end_minute": 18 * 60, "continuous_riding_minutes": 0.0, "break_until_minute": None,
                    "delay_until_minute": None, "heat_rule_alert": False, "status": "ONLINE", "updated_at": _utc_now(),
                }

            for index, destination in enumerate(destinations, start=1):
                client_id = f"demo-client-{index}"
                origin = origins[(index - 1) % len(origins)]
                distance = round(haversine_km(origin[0], origin[1], destination[0], destination[1]) * 1.24, 2)
                self.users[client_id] = {"id": client_id, "name": f"Demo Client {index}", "email": f"{client_id}@rumbo.demo", "role": "client", "registered_at": _utc_now()}
                order = LiveOrder(
                    id=f"DEMO-{index:03d}", client_id=client_id, client_name=f"Demo Client {index}",
                    restaurant=f"Rumbo Kitchen {((index - 1) % 3) + 1}", origin=origin, destination=destination,
                    destination_label=f"Monterrey stop {index}", location=destination, items=[{"id": "demo-meal", "quantity": 1}],
                    status="MATCHED",
                    distance_km=distance, eta_minutes=round(max(3, distance * 3.5), 1),
                    delivery_fee_mxn=round(39 + distance * 8.5, 2), courier_payout_mxn=round(35 + distance * 7.25, 2),
                    platform_commission_mxn=round(max(0, 4 + distance * 1.25), 2), tip_mxn=50 if index % 4 == 0 else (index % 4) * 15,
                    weight_kg=3.0, volume_liters=4.0,
                    route_geometry=[[origin[1], origin[0]], [destination[1], destination[0]]], street_names=["Monterrey street mesh"],
                )
                eligible = [driver for driver in self.drivers.values() if driver["id"].startswith("demo-") and len(driver["assigned_order_ids"]) < 3 and self._fits_capacity(driver, order)]
                driver = min(eligible, key=lambda item: haversine_km(item["position"][0], item["position"][1], origin[0], origin[1]))
                order.driver_id = driver["id"]
                order.courier_route_geometry = [[driver["position"][1], driver["position"][0]], [origin[1], origin[0]]]
                order.courier_distance_km = round(haversine_km(driver["position"][0], driver["position"][1], origin[0], origin[1]) * 1.24, 2)
                order.courier_eta_minutes = round(max(2, order.courier_distance_km * 3.5), 1)
                order.courier_street_names = ["Monterrey street mesh"]
                driver["assigned_order_ids"].append(order.id)
                self.orders[order.id] = order
                alternate = next((item for item in self.drivers.values() if item["id"] != driver["id"]), None)
                tags = ["PROFIT OPTIMIZED"]
                if order.tip_mxn >= 50:
                    tags.append("TIP PRIORITIZED")
                if index in {5, 11}:
                    tags.append("VEHICLE CAPACITY BLOCKED")
                if index == 13:
                    tags.append("HEAT RULE BLOCKED")
                if index == 15:
                    tags.append("FLAGGED ZONE PREVENTED")
                alternate_eta = round(max(order.courier_eta_minutes + 1.8, 2), 1)
                self._remember_decision({
                    "id": f"demo-decision-{index:03d}", "order_ids": [order.id],
                    "selected_driver_id": driver["id"], "origin": origin, "destination": destination,
                    "candidates": [
                        {"driver_id": driver["id"], "name": driver["name"], "vehicle": driver["vehicle_profile"],
                         "distance_km": order.courier_distance_km, "eta_minutes": order.courier_eta_minutes,
                         "penalty": "Clear corridor", "selected": True},
                        *([{ "driver_id": alternate["id"], "name": alternate["name"],
                             "vehicle": alternate["vehicle_profile"], "distance_km": round(order.courier_distance_km + .8, 2),
                             "eta_minutes": alternate_eta, "penalty": "Longer OSRM approach", "selected": False}] if alternate else []),
                    ],
                    "tags": tags,
                    "reason": f"Selected {driver['name']} ({driver['vehicle_profile']}, ETA {order.courier_eta_minutes:.1f} min) over the next OSRM candidate; "
                              f"{('$50 MXN tip prioritized. ' if order.tip_mxn >= 50 else '')}the route keeps the highlighted demo within safety and capacity constraints.",
                    "created_at": _utc_now(),
                })
            return self.snapshot()

    async def advance(self, real_seconds: float = 0.5, simulated_minutes: float | None = None) -> list[dict]:
        """Advance server-side courier snapshots; browsers interpolate them at 60 FPS."""
        async with self._lock:
            previous_minute = self.simulation_minutes
            if simulated_minutes is None:
                self.simulation_minutes += real_seconds * TIME_WARP / 60
            else:
                self.simulation_minutes = float(simulated_minutes)
            elapsed_simulated_minutes = max(0.0, self.simulation_minutes - previous_minute)
            updates: list[dict] = []
            for driver_id, driver in self.drivers.items():
                if not driver.get("online"):
                    continue
                self._refresh_driver_status(driver)
                if driver.get("status") in {"DELAYED", "ON_BREAK", "OFF_SHIFT"}:
                    continue
                active_orders = [
                    self.orders[order_id] for order_id in driver["assigned_order_ids"]
                    if order_id in self.orders and self.orders[order_id].status in {"MATCHED", "IN_TRANSIT"}
                ]
                if not active_orders:
                    continue
                driver["continuous_riding_minutes"] = driver.get("continuous_riding_minutes", 0.0) + elapsed_simulated_minutes
                clock_minute = _minutes_in_day(self.simulation_minutes)
                heat_window = 12 * 60 <= clock_minute <= 16 * 60
                if heat_window and driver["continuous_riding_minutes"] >= 90:
                    driver["heat_rule_alert"] = True
                    driver["break_until_minute"] = self.simulation_minutes + 20
                    driver["status"] = "ON_BREAK"
                    driver["is_available"] = False
                    continue
                if driver["continuous_riding_minutes"] >= 240:
                    driver["break_until_minute"] = self.simulation_minutes + 20
                    driver["status"] = "ON_BREAK"
                    driver["is_available"] = False
                    continue
                active = active_orders[0]
                batch = self.batches.get(active.batch_id or "")
                batch_orders = [self.orders[order_id] for order_id in batch.order_ids if order_id in self.orders] if batch else []
                vehicle_key = self._vehicle_key(driver.get("vehicle_profile") or driver.get("vehicle"))
                seconds_per_km = VEHICLE_SECONDS_PER_KM[vehicle_key]
                display_speed = VEHICLE_DISPLAY_SPEED_KMH[vehicle_key]
                if active.status == "MATCHED":
                    # Phase one: the courier follows the server-calculated OSRM
                    # approach route to the restaurant before delivery begins.
                    geometry = active.courier_route_geometry
                    if len(geometry) < 2:
                        continue
                    route_seconds = max(active.courier_distance_km * seconds_per_km, .01)
                    key = f"_approach_{batch.id if batch else active.id}"
                    progress = min(1.0, driver.get(key, 0.0) + real_seconds / route_seconds)
                    driver[key] = progress
                    position, bearing = _point_on_geometry(geometry, progress)
                    street_names = active.courier_street_names
                    street_index = min(len(street_names) - 1, int(progress * len(street_names))) if street_names else 0
                    telemetry = {
                        "driver_id": driver_id, "position": position, "bearing": round(bearing, 1),
                        "street_name": street_names[street_index] if street_names else "",
                        "speed_kmh": display_speed, "order_id": active.id, "phase": "COURIER_TO_STORE",
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
                    route_seconds = max(batch.batch_distance_km * seconds_per_km, .01)
                    key = f"_progress_{batch.id}"
                    street_names = [name for order in batch_orders for name in order.street_names]
                else:
                    geometry = active.route_geometry or [[active.origin[1], active.origin[0]], [active.destination[1], active.destination[0]]]
                    route_seconds = max(active.distance_km * seconds_per_km, .01)
                    key = f"_progress_{active.id}"
                    street_names = active.street_names
                progress = min(1.0, driver.get(key, 0.0) + real_seconds / route_seconds)
                driver[key] = progress
                # This is intentionally distance-weighted interpolation on the
                # OSRM geometry itself, never a shortcut between destinations.
                position, bearing = _point_on_geometry(geometry, progress)
                street_index = min(len(street_names) - 1, int(progress * len(street_names))) if street_names else 0
                telemetry = {
                    "driver_id": driver_id, "position": position, "bearing": round(bearing, 1),
                    "street_name": street_names[street_index] if street_names else "",
                    "speed_kmh": display_speed, "order_id": active.id, "phase": "STORE_TO_CLIENT",
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
            # The event engine owns the environment. Keep that latest state in the
            # central coordinator so subsequent dispatches score the same conditions.
            self.traffic = traffic.model_copy(deep=True) if traffic else TrafficState()
            self.weather = weather.model_copy(deep=True) if weather else WeatherState()

            active_orders = [
                order for order in self.orders.values()
                if order.status in {"PENDING", "MATCHED", "IN_TRANSIT"}
            ]
            added_minutes: list[float] = []
            # Refresh every active order's customer-facing ETA with the exact same
            # sector-aware route-cost policy used to choose a courier.
            for order in active_orders:
                previous_eta = order.eta_minutes
                direct, _ = await self._conditioned_route(order.origin, order.destination)
                order.distance_km = round(direct.distance_km, 2)
                order.eta_minutes = round(direct.duration_minutes, 1)
                order.route_geometry = direct.geometry
                order.street_names = direct.street_names
                order.delivery_fee_mxn = round(39 + direct.distance_km * 8.5, 2)
                added_minutes.append(max(0.0, order.eta_minutes - previous_eta))

            impact_minutes = round(max(added_minutes, default=0.0), 1)
            impact_label = {
                "TORRENTIAL_RAIN": "torrential rain",
                "SAN_PEDRO_CONGESTION": "San Pedro congestion",
                "GONZALITOS_FLOOD": "Gonzalitos flooding",
                "ROAD_CLOSURE": "road closure",
                "NORMAL_TRAFFIC": "normal traffic",
            }.get(disruption, "traffic conditions")
            self.traffic_impact = {
                "minutes": impact_minutes,
                "event": disruption,
                "message": "Normal traffic conditions." if disruption == "NORMAL_TRAFFIC" else f"+{impact_minutes:.1f} min due to {impact_label}.",
            }

            # A closure or weather event also changes the approach leg. Refresh
            # it for every assigned active courier, not just a batch route.
            refreshed_drivers: set[str] = set()
            for order in active_orders:
                if order.driver_id and order.driver_id not in refreshed_drivers:
                    await self._attach_courier_route([order])
                    refreshed_drivers.add(order.driver_id)

            if not self.batch:
                return None

            orders = [self.orders[order_id] for order_id in self.batch.order_ids if order_id in self.orders]
            if len(orders) == 2:
                # Re-query the batch's street geometry using the central condition
                # state. A sector penalty affects only candidates and legs that cross
                # the affected corridor; torrential rain changes every route's ETA.
                first, second = sorted(orders, key=lambda order: order.distance_km)
                leg_one, _ = await self._conditioned_route(first.origin, first.destination)
                leg_two, _ = await self._conditioned_route(first.destination, second.destination)
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
                "NORMAL_TRAFFIC": "Tráfico normal: Rumbo restauró los ETA base de la red vial.",
            }
            self.batch.reasoning = f"{impacts.get(disruption, 'Rumbo Edge actualizó la recomendación con el nuevo estado vial.')} Ruta y ETA recalculados; {self.batch.savings_percent:.1f}% de ahorro calculado."
            self.batch.status = f"RECALCULATED_{disruption}"
            return self.batch
