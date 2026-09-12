"""FastAPI application factory for the Raspberry Pi edge server."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edge_server.api import demo, health, websocket
from edge_server.config import get_settings
from edge_server.data.telemetry_service import TelemetryService
from edge_server.data.tiger_db import TigerDB
from edge_server.logging_config import configure_logging
from edge_server.simulation.simulation_engine import SimulationEngine
from edge_server.websocket_manager import ConnectionManager


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        app.state.settings = settings
        app.state.connections = ConnectionManager()
        telemetry = TelemetryService(TigerDB(settings.tiger_db_url, settings.use_tiger))
        await telemetry.start()
        app.state.engine = SimulationEngine(settings, telemetry, app.state.connections.broadcast)
        yield
        await app.state.engine.stop()
        await telemetry.close()

    app = FastAPI(title="Courier Edge Decision System", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    @app.get("/", tags=["root"])
    async def root() -> dict:
        return {"service": "Courier Edge Decision System", "docs": "/docs", "health": "/health", "websocket": "/ws"}

    app.include_router(health.router)
    app.include_router(demo.router)
    app.include_router(websocket.router)
    return app


app = create_app()
