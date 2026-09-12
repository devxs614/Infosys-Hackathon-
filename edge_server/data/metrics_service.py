"""Pure metrics calculation used by REST, WebSocket, and tests."""
from __future__ import annotations

from edge_server.models import DriverState


class MetricsService:
    @staticmethod
    def for_driver(driver: DriverState) -> dict[str, float | int]:
        elapsed_hours = max(driver.shift_minutes_elapsed / 60, 1 / 60)
        attempts = driver.accepted_orders + driver.rejected_orders
        return {
            "gross_earnings_mxn": round(driver.earnings_mxn, 2),
            "net_earnings_mxn": round(driver.earnings_mxn, 2),
            "distance_km": round(driver.distance_km, 2),
            "duration_minutes": round(driver.shift_minutes_elapsed, 2),
            "orders_completed": driver.completed_orders,
            "late_orders": driver.late_orders,
            "mxn_per_hour": round(driver.earnings_mxn / elapsed_hours, 2),
            "mxn_per_km": round(driver.earnings_mxn / max(driver.distance_km, .01), 2),
            "average_order_value": round(driver.earnings_mxn / max(driver.completed_orders, 1), 2),
            "acceptance_rate": round(driver.accepted_orders / max(attempts, 1), 3),
            "rejection_rate": round(driver.rejected_orders / max(attempts, 1), 3),
            "batch_rate": round(driver.batches / max(driver.accepted_orders, 1), 3),
        }

    @staticmethod
    def comparison(baseline: DriverState, ai: DriverState) -> dict[str, float]:
        baseline_metrics = MetricsService.for_driver(baseline)
        ai_metrics = MetricsService.for_driver(ai)
        def change(key: str) -> float:
            base = float(baseline_metrics[key])
            value = float(ai_metrics[key])
            return round((value - base) / base, 4) if base else 0.0
        return {
            "earnings_improvement": change("gross_earnings_mxn"),
            "hourly_improvement": change("mxn_per_hour"),
            "distance_efficiency_improvement": change("mxn_per_km"),
            "late_order_change": float(ai.late_orders - baseline.late_orders),
        }
