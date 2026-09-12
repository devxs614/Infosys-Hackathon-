import pytest

from edge_server.data.telemetry_service import TelemetryService
from edge_server.data.tiger_db import TigerDB
from edge_server.models import Telemetry


@pytest.mark.asyncio
async def test_tiger_disabled_retains_telemetry_in_memory():
    service = TelemetryService(TigerDB(enabled=False))
    await service.start()
    await service.record(Telemetry(simulation_time=1, driver_id="d", agent_type="test", decision="WAIT", lat=0, lon=0,
                                   distance=0, duration=1, earnings=0, traffic=1, weather=0, temperature=25, surge=1, late_orders=0))
    assert service.database.pool is None
    assert len(service.memory) == 1
