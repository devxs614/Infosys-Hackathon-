"""Judge-friendly simulation controls."""
from fastapi import APIRouter, Request

from edge_server.models import JudgeEvent

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/start")
async def start_demo(request: Request) -> dict:
    await request.app.state.engine.start()
    return {"status": "started", "state": request.app.state.engine.state().model_dump(mode="json")}


@router.post("/stop")
async def stop_demo(request: Request) -> dict:
    await request.app.state.engine.stop()
    return {"status": "stopped", "state": request.app.state.engine.state().model_dump(mode="json")}


@router.post("/reset")
async def reset_demo(request: Request) -> dict:
    await request.app.state.engine.reset()
    return {"status": "reset", "state": request.app.state.engine.state().model_dump(mode="json")}


@router.post("/trigger")
async def trigger_demo(event: JudgeEvent, request: Request) -> dict:
    await request.app.state.engine.trigger(event)
    batch = await request.app.state.live_orders.recalculate(event.event_type.value)
    if batch:
        await request.app.state.connections.broadcast("AI_BATCH_SUGGESTION", batch.model_dump(mode="json"))
    return {"status": "triggered", "event": event.model_dump()}


@router.get("/state")
async def demo_state(request: Request) -> dict:
    return request.app.state.engine.state().model_dump(mode="json")


@router.post("/judge-event")
async def judge_event(event: JudgeEvent, request: Request) -> dict:
    await request.app.state.engine.trigger(event)
    batch = await request.app.state.live_orders.recalculate(event.event_type.value)
    if batch:
        await request.app.state.connections.broadcast("AI_BATCH_SUGGESTION", batch.model_dump(mode="json"))
    return {"status": "accepted", "event": event.model_dump()}
