"""Validate an LLM proposal before it can change the simulated world."""
from __future__ import annotations

from dataclasses import dataclass

from edge_server.models import Decision, DecisionType, DriverState, Order


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    reason: str = ""


class DecisionValidator:
    max_batch_size = 2

    def validate(self, decision: Decision, driver: DriverState, available_orders: list[Order],
                 simulation_minute: float, time_remaining: float) -> ValidationResult:
        ids = decision.selected_order_ids
        available = {order.id: order for order in available_orders}
        if decision.decision_type in {DecisionType.ACCEPT, DecisionType.BATCH} and not ids:
            return ValidationResult(False, "accept and batch decisions require order IDs")
        if decision.decision_type == DecisionType.BATCH and len(ids) < 2:
            return ValidationResult(False, "batch decisions require two orders")
        if len(ids) > self.max_batch_size:
            return ValidationResult(False, "batch capacity exceeded")
        if any(order_id not in available for order_id in ids):
            return ValidationResult(False, "decision references unavailable order")
        if not driver.available and decision.decision_type in {DecisionType.ACCEPT, DecisionType.BATCH}:
            return ValidationResult(False, "driver is busy")
        if decision.estimated_profit_mxn > 10000 or decision.estimated_duration_minutes > 600:
            return ValidationResult(False, "unrealistic estimate")
        if decision.estimated_duration_minutes > time_remaining + 0.01:
            return ValidationResult(False, "decision exceeds remaining shift")
        selected = [available[order_id] for order_id in ids]
        if any(order.delivery_deadline < simulation_minute for order in selected):
            return ValidationResult(False, "order deadline already expired")
        if decision.decision_type == DecisionType.REPOSITION and (decision.reposition_lat is None or decision.reposition_lon is None):
            return ValidationResult(False, "reposition requires a coordinate")
        return ValidationResult(True)
