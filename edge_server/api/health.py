"""Operational health endpoint."""
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    settings = request.app.state.settings
    engine = request.app.state.engine
    return {
        "status": "ok", "service": "courier-edge-decision-system", "environment": settings.app_env,
        "simulation_running": engine.running, "websocket_clients": request.app.state.connections.count,
        "fallbacks": {"gemini": not engine.gemini_agent.enabled, "tiger_memory": engine.telemetry.database.pool is None,
                      "routing_fallback_available": True},
    }

