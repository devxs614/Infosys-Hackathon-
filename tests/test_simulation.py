import pytest

from edge_server.config import Settings
from edge_server.data.telemetry_service import TelemetryService
from edge_server.data.tiger_db import TigerDB
from edge_server.simulation.clock import SimulationClock
from edge_server.simulation.simulation_engine import SimulationEngine


def test_clock_compresses_shift():
    clock = SimulationClock(shift_minutes=240, demo_seconds=180, tick_ms=500)
    assert round(clock.minutes_per_tick, 3) == round(240 / 360, 3)
    clock.tick()
    assert clock.current_minute > 0


@pytest.mark.asyncio
async def test_two_worlds_receive_the_same_initial_scenario():
    telemetry = TelemetryService(TigerDB(enabled=False))
    engine = SimulationEngine(Settings(use_osrm=False, use_gemini=False, use_tiger=False, tick_ms=10), telemetry)
    await engine.step()
    assert set(engine.baseline_world.orders) == set(engine.ai_world.orders)
    assert len(telemetry.memory) == 2

