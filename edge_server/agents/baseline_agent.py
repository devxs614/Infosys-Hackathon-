"""Defensible reactive driver: evaluates individual offers only."""
from __future__ import annotations

from edge_server.agents.base_agent import BaseAgent
from edge_server.models import Decision, DecisionType, DriverState, Order, TrafficState, WeatherState


class BaselineAgent(BaseAgent):
    agent_name = "baseline"

    @staticmethod
    def score(order: Order, simulation_minute: float, traffic: TrafficState) -> float:
        """Current-offer payout/hour with distance and deadline pressure penalties."""
        time_cost = order.estimated_minutes * traffic.global_factor
        hourly_value = order.courier_payout_mxn * 60 / max(time_cost, 1)
        distance_penalty = order.distance_km * 2.5
        slack = order.delivery_deadline - simulation_minute - time_cost
        deadline_penalty = 20 if slack < 0 else (8 if slack < 8 else 0)
        return hourly_value - distance_penalty - deadline_penalty

    async def decide(self, driver: DriverState, orders: list[Order], traffic: TrafficState,
                     weather: WeatherState, simulation_minute: float, time_remaining: float) -> Decision:
        if not orders or not driver.available:
            return Decision(decision_type=DecisionType.WAIT, reasoning="No available single order to evaluate.",
                            estimated_profit_mxn=0, estimated_distance_km=0, estimated_duration_minutes=1, confidence=.9)
        candidate = max(orders, key=lambda order: self.score(order, simulation_minute, traffic))
        score = self.score(candidate, simulation_minute, traffic)
        if score < 35 or candidate.estimated_minutes > time_remaining:
            return Decision(decision_type=DecisionType.REJECT, selected_order_ids=[candidate.id],
                            reasoning="Current payout-to-time value is below the reactive acceptance threshold.",
                            estimated_profit_mxn=0, estimated_distance_km=0,
                            estimated_duration_minutes=candidate.estimated_minutes, confidence=.75)
        return Decision(decision_type=DecisionType.ACCEPT, selected_order_ids=[candidate.id],
                        reasoning="Best immediate payout-to-time offer after distance and deadline checks.",
                        estimated_profit_mxn=candidate.courier_payout_mxn, estimated_distance_km=candidate.distance_km,
                        estimated_duration_minutes=candidate.estimated_minutes * traffic.global_factor, confidence=.78)

