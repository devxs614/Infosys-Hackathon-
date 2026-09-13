"""FastAPI application factory for the Raspberry Pi edge server."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edge_server.api import auth, demo, health, routes, security_decisions, websocket
from edge_server.config import get_settings
from edge_server.data.auth_store import AuthStore
from edge_server.data.telemetry_service import TelemetryService
from edge_server.data.tiger_db import TigerDB
from edge_server.logging_config import configure_logging
from edge_server.live_order_service import LiveOrderCoordinator
from edge_server.routing.routing_engine import RoutingEngine
from edge_server.simulation.simulation_engine import SimulationEngine
from edge_server.websocket_manager import ConnectionManager


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        app.state.settings = settings
        app.state.connections = ConnectionManager()
        app.state.auth_store = AuthStore(settings.auth_db_path)
        app.state.auth_store.connect()
        telemetry = TelemetryService(TigerDB(settings.tiger_db_url, settings.use_tiger))
        await telemetry.start()
        app.state.engine = SimulationEngine(settings, telemetry, app.state.connections.broadcast)
        app.state.routing = RoutingEngine(settings.osrm_url, settings.use_osrm)
        app.state.live_orders = LiveOrderCoordinator(app.state.engine.gemini_agent, app.state.routing)
        app.state.decision_explanations = {}
        telemetry_stop = asyncio.Event()

        async def advance_live_mesh() -> None:
            while not telemetry_stop.is_set():
                await asyncio.sleep(0.5)
                updates = await app.state.live_orders.advance(0.5)
                for update in updates:
                    await app.state.connections.broadcast("DRIVER_TELEMETRY", update)
                    await app.state.connections.broadcast("DRIVER_FINANCIAL_UPDATE", app.state.live_orders.driver_financial_update(update["driver_id"]))
                if updates:
                    await app.state.connections.broadcast("LIVE_ORDER_STATE", app.state.live_orders.snapshot())
                await app.state.connections.broadcast("VERDICT_EVALUATION", app.state.live_orders.verdict_evaluation())
                await app.state.connections.broadcast("LIVE_METRICS", app.state.live_orders.snapshot()["metrics"])

        telemetry_task = asyncio.create_task(advance_live_mesh(), name="rumbo-live-telemetry")
        yield
        telemetry_stop.set()
        telemetry_task.cancel()
        with suppress(asyncio.CancelledError):
            await telemetry_task
        await app.state.engine.stop()
        await telemetry.close()
        app.state.auth_store.close()

    app = FastAPI(title="Rumbo | Edge Logistics OS", version="0.2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    @app.get("/", tags=["root"])
    async def root() -> dict:
        return {"service": "Rumbo | Edge Logistics OS", "docs": "/docs", "health": "/health", "websocket": "/ws"}

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(demo.router)
    app.include_router(routes.router)
    app.include_router(security_decisions.router)
    app.include_router(websocket.router)
    return app


app = create_app()
