"""Async fair-comparison simulation loop used by API endpoints and WebSockets."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from edge_server.agents.baseline_agent import BaselineAgent
from edge_server.agents.decision_validator import DecisionValidator
from edge_server.agents.gemini_agent import GeminiAgent
from edge_server.config import Settings
from edge_server.data.metrics_service import MetricsService
from edge_server.data.telemetry_service import TelemetryService
from edge_server.models import Decision, DecisionType, Disruption, DriverState, EventType, JudgeEvent, OrderStatus, SimulationState, Telemetry
from edge_server.routing.routing_engine import RoutingEngine
from edge_server.simulation.clock import SimulationClock
from edge_server.simulation.event_engine import EventEngine
from edge_server.simulation.order_generator import ZONES
from edge_server.simulation.scenario_engine import ScenarioStream
from edge_server.simulation.world_state import ActiveTrip, DriverWorld

logger = logging.getLogger(__name__)
Publisher = Callable[[str, dict], Awaitable[None]]


class SimulationEngine:
    """Runs two independent driver worlds from one immutable, seeded ScenarioStream."""

    def __init__(self, settings: Settings, telemetry: TelemetryService, publisher: Publisher | None = None) -> None:
        self.settings = settings
        self.telemetry = telemetry
        self.publisher = publisher
        self.clock = SimulationClock(settings.shift_minutes, settings.demo_seconds, settings.tick_ms)
        self.scenario = ScenarioStream(settings.scenario_seed, settings.shift_minutes)
        self.event_engine = EventEngine()
        self.routing = RoutingEngine(settings.osrm_url, settings.use_osrm)
        self.baseline_agent = BaselineAgent()
        self.gemini_agent = GeminiAgent(settings.gemini_api_key, settings.gemini_model, settings.use_gemini)
        self.validator = DecisionValidator()
        self.running = False
        self._task: asyncio.Task[None] | None = None
        self._automatic_events: list[Disruption] = []
        self.baseline_world, self.ai_world = self._new_worlds()

    def _new_worlds(self) -> tuple[DriverWorld, DriverWorld]:
        origin = ZONES["Macroplaza"]
        baseline = DriverState(driver_id="baseline", lat=origin[0], lon=origin[1])
        ai = DriverState(driver_id="gemini", lat=origin[0], lon=origin[1])
        return DriverWorld(baseline), DriverWorld(ai)

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="courier-simulation")
        logger.info("Simulation started")
        await self._publish("event", {"message": "Simulation started", "event_type": "START"})

    async def stop(self) -> None:
        self.running = False
        task = self._task
        self._task = None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Simulation stopped")
        await self._publish("event", {"message": "Simulation stopped", "event_type": "STOP"})

    async def reset(self) -> None:
        await self.stop()
        self.clock.reset()
        self.scenario = ScenarioStream(self.settings.scenario_seed, self.settings.shift_minutes)
        self.event_engine = EventEngine()
        self._automatic_events = []
        self.baseline_world, self.ai_world = self._new_worlds()
        await self._publish("simulation_state", self.state().model_dump(mode="json"))

    async def _loop(self) -> None:
        try:
            while self.running and not self.clock.finished:
                await self.step()
                await asyncio.sleep(self.settings.tick_ms / 1000)
            if self.clock.finished:
                self.running = False
                await self._publish("event", {"message": "Shift completed", "event_type": "COMPLETE"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Simulation loop error")
            self.running = False
            await self._publish("error", {"message": str(exc)})

    async def step(self) -> None:
        """Advance one deterministic tick; useful directly in offline tests."""
        previous = self.clock.current_minute
        delta = self.clock.tick()
        tick = self.scenario.tick(previous, self.clock.current_minute)
        self._automatic_events.extend(tick.events)
        active_events = self.event_engine.all_active(self._automatic_events)
        weather, traffic = self.event_engine.conditions(active_events)
        for world in (self.baseline_world, self.ai_world):
            world.add_orders(tick.orders)
            world.weather, world.traffic, world.events = weather.model_copy(deep=True), traffic.model_copy(deep=True), [e.model_copy(deep=True) for e in active_events]
            if any(event.event_type == EventType.SAN_PEDRO_SURGE for event in active_events):
                for order in world.orders.values():
                    if order.zone == "San Pedro" and order.status == OrderStatus.AVAILABLE:
                        order.surge_multiplier = max(order.surge_multiplier, 2.3)
            world.driver.shift_minutes_elapsed = self.clock.current_minute
            await self._advance_trip(world, delta)
        for world, agent, label in ((self.baseline_world, self.baseline_agent, "baseline"), (self.ai_world, self.gemini_agent, "gemini")):
            if world.driver.available:
                await self._decide_and_execute(world, agent, label)
            telemetry = await self._record_telemetry(world, label)
            await self._publish("driver_update", {"agent": label, "driver": world.driver.model_dump(mode="json")})
            await self._publish("order_update", {"agent": label, "orders": [order.model_dump(mode="json") for order in world.orders.values()]})
            await self._publish("telemetry", telemetry.model_dump(mode="json"))
        await self._publish("simulation_state", self.state().model_dump(mode="json"))
        await self._publish("metrics", self.state().metrics)

    async def _advance_trip(self, world: DriverWorld, delta: float) -> None:
        trip = world.trip
        if trip is None:
            return
        trip.remaining_minutes -= delta
        if trip.remaining_minutes > 0:
            return
        driver = world.driver
        driver.lat, driver.lon = trip.final_lat, trip.final_lon
        driver.distance_km += trip.distance_km
        driver.available = True
        driver.current_order_ids = []
        for order_id in trip.order_ids:
            order = world.orders[order_id]
            order.status = OrderStatus.COMPLETED
            driver.earnings_mxn += order.courier_payout_mxn
            driver.completed_orders += 1
            if self.clock.current_minute > order.delivery_deadline:
                driver.late_orders += 1
        world.trip = None

    async def _decide_and_execute(self, world: DriverWorld, agent: object, label: str) -> None:
        available = world.available_orders(self.clock.current_minute)
        time_left = self.settings.shift_minutes - self.clock.current_minute
        decision = await agent.decide(world.driver, available, world.traffic, world.weather, self.clock.current_minute, time_left)  # type: ignore[attr-defined]
        if label == "gemini":
            result = self.validator.validate(decision, world.driver, available, self.clock.current_minute, time_left)
            if not result.valid:
                logger.warning("Gemini decision invalid, using fallback: %s", result.reason)
                decision = self.gemini_agent.fallback_decide(world.driver, available, world.traffic, world.weather, self.clock.current_minute, time_left)
        world.last_decision = decision
        await self._execute(world, decision)
        await self._publish("decision", {"agent": label, "decision": decision.model_dump(mode="json")})

    async def _execute(self, world: DriverWorld, decision: Decision) -> None:
        driver = world.driver
        if decision.decision_type == DecisionType.REJECT:
            for order_id in decision.selected_order_ids:
                if order_id in world.orders:
                    world.orders[order_id].status = OrderStatus.REJECTED
                    driver.rejected_orders += 1
            return
        if decision.decision_type == DecisionType.WAIT:
            return
        if decision.decision_type == DecisionType.REPOSITION:
            # Reposition is modeled as a zero-revenue trip, never a magic location update.
            destination = (decision.reposition_lat or driver.lat, decision.reposition_lon or driver.lon)
            route = await self.routing.estimate((driver.lat, driver.lon), destination, world.traffic, world.weather)
            if route.feasible:
                driver.available = False
                world.trip = ActiveTrip([], route.duration_minutes, route.duration_minutes, route.distance_km, destination[0], destination[1], decision)
            return
        selected = [world.orders[order_id] for order_id in decision.selected_order_ids if order_id in world.orders]
        if not selected:
            return
        origin = (driver.lat, driver.lon)
        legs: list[tuple[tuple[float, float], tuple[float, float], str]] = []
        for order in selected:
            pickup = (order.pickup_lat, order.pickup_lon)
            dropoff = (order.dropoff_lat, order.dropoff_lon)
            legs.extend([(origin, pickup, order.zone), (pickup, dropoff, order.zone)])
            origin = dropoff
        # External OSRM calls are concurrent and independently capped; one slow provider cannot serially stall a tick.
        routes = await asyncio.gather(*[
            self.routing.estimate(start, end, world.traffic, world.weather, zone)
            for start, end, zone in legs
        ])
        total_distance, total_duration = 0.0, 0.0
        for index, order in enumerate(selected):
            first, second = routes[index * 2], routes[index * 2 + 1]
            if not first.feasible or not second.feasible:
                return
            total_distance += first.distance_km + second.distance_km
            total_duration += first.duration_minutes + second.duration_minutes
        for order in selected:
            order.status = OrderStatus.ACCEPTED
        driver.current_order_ids = [order.id for order in selected]
        driver.available = False
        driver.accepted_orders += len(selected)
        if len(selected) == 2:
            driver.batches += 1
        world.trip = ActiveTrip([o.id for o in selected], max(total_duration, .1), max(total_duration, .1), total_distance, origin[0], origin[1], decision)
        logger.info("%s decision %s for %s", driver.driver_id, decision.decision_type.value, driver.current_order_ids)

    async def _record_telemetry(self, world: DriverWorld, agent_type: str) -> Telemetry:
        decision = world.last_decision
        event = Telemetry(simulation_time=self.clock.current_minute, driver_id=world.driver.driver_id, agent_type=agent_type,
                          decision=decision.decision_type.value if decision else "WAIT",
                          order_ids=decision.selected_order_ids if decision else [], lat=world.driver.lat, lon=world.driver.lon,
                          distance=world.driver.distance_km, duration=world.driver.shift_minutes_elapsed,
                          earnings=world.driver.earnings_mxn, traffic=world.traffic.global_factor,
                          weather=world.weather.rain_intensity, temperature=world.weather.temperature_c,
                          surge=max((o.surge_multiplier for o in world.orders.values()), default=1.0), late_orders=world.driver.late_orders)
        await self.telemetry.record(event)
        return event

    async def trigger(self, judge_event: JudgeEvent) -> None:
        zone = judge_event.zone or {EventType.GONZALITOS_FLOOD: "Gonzalitos", EventType.SAN_PEDRO_SURGE: "San Pedro", EventType.SAN_PEDRO_CONGESTION: "San Pedro",
                                    EventType.ROAD_CLOSURE: "Obispado"}.get(judge_event.event_type, "Monterrey")
        event = Disruption(id=f"MANUAL-{judge_event.event_type.value}", event_type=judge_event.event_type, zone=zone,
                           start_minute=self.clock.current_minute, active=judge_event.active, description=f"Judge triggered {judge_event.event_type.value}")
        self.event_engine.trigger(event)
        await self._publish("event", event.model_dump(mode="json"))

    def state(self) -> SimulationState:
        baseline_metrics = MetricsService.for_driver(self.baseline_world.driver)
        ai_metrics = MetricsService.for_driver(self.ai_world.driver)
        return SimulationState(running=self.running, scenario_seed=self.settings.scenario_seed, simulation_minute=self.clock.current_minute,
            shift_minutes=self.settings.shift_minutes, baseline=self.baseline_world.driver, ai_driver=self.ai_world.driver,
            orders=list(self.ai_world.orders.values()), weather=self.ai_world.weather, traffic=self.ai_world.traffic,
            events=self.ai_world.events, last_decisions={"baseline": self.baseline_world.last_decision, "gemini": self.ai_world.last_decision},
            metrics={"baseline": baseline_metrics, "ai": ai_metrics, "comparison": MetricsService.comparison(self.baseline_world.driver, self.ai_world.driver)})

    async def _publish(self, message_type: str, data: dict) -> None:
        if self.publisher:
            await self.publisher(message_type, data)
