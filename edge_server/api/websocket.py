"""WebSocket endpoint for local dashboard updates."""
from __future__ import annotations

from pydantic import ValidationError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


def _validation_details(error: ValidationError) -> list[dict[str, object]]:
    """Pydantic may retain a Python exception in `ctx`; WebSocket frames must stay JSON-safe."""
    return [{"loc": list(item["loc"]), "message": item["msg"], "type": item["type"]} for item in error.errors()]


@router.websocket("/ws")
async def simulation_websocket(websocket: WebSocket) -> None:
    manager = websocket.app.state.connections
    await manager.connect(websocket)
    try:
        await manager.send(websocket, "connection", {"status": "connected", "transport": "websocket"})
        await manager.send(websocket, "hello_response", {"service": "Rumbo | Edge Logistics OS", "state": websocket.app.state.engine.state().model_dump(mode="json")})
        await manager.send(websocket, "live_order_state", websocket.app.state.live_orders.snapshot())
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            payload = message.get("data", message)
            if message_type == "ping":
                await manager.send(websocket, "pong", {})
            elif message_type in {"REGISTER_USER", "USER_REGISTERED", "DRIVER_ONLINE"}:
                try:
                    registration = await websocket.app.state.live_orders.register_user(payload)
                    await manager.broadcast("USER_REGISTERED", registration)
                    if registration.get("driver"):
                        await manager.broadcast("DRIVER_ONLINE", {"driver": registration["driver"], "metrics": registration["metrics"]})
                        for order_id in registration.get("matched_order_ids", []):
                            match_payload = websocket.app.state.live_orders.order_match_payload(websocket.app.state.live_orders.orders[order_id])
                            if match_payload:
                                await manager.broadcast("ORDER_MATCHED", match_payload)
                        await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(registration["driver"]["id"]))
                        await manager.broadcast("VERDICT_EVALUATION", websocket.app.state.live_orders.verdict_evaluation())
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid REGISTER_USER", "details": _validation_details(exc)})
            elif message_type == "NEW_ORDER":
                try:
                    order, batch = await websocket.app.state.live_orders.create_order(payload)
                    await manager.broadcast("NEW_ORDER", {"order": order.model_dump(mode="json")})
                    matched_orders = [order]
                    if batch:
                        matched_orders = [websocket.app.state.live_orders.orders[order_id] for order_id in batch.order_ids if order_id in websocket.app.state.live_orders.orders]
                    for matched_order in matched_orders:
                        match_payload = websocket.app.state.live_orders.order_match_payload(matched_order)
                        if match_payload:
                            await manager.broadcast("ORDER_MATCHED", match_payload)
                            await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(matched_order.driver_id))
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                    if batch:
                        batch_data = batch.model_dump(mode="json")
                        await manager.broadcast("AI_BATCH_SUGGESTION", batch_data)
                        await manager.broadcast("AI_BATCH_OPTIMIZATION", batch_data)
                        await manager.broadcast("DRIVER_NOTIFICATION", {
                            "title": "Rumbo AI detectó un batch",
                            "batch": batch_data,
                        })
                    await manager.broadcast("VERDICT_EVALUATION", websocket.app.state.live_orders.verdict_evaluation())
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid NEW_ORDER", "details": _validation_details(exc)})
            elif message_type == "DRIVER_ACTION":
                try:
                    batch, orders = await websocket.app.state.live_orders.apply_driver_action(payload)
                    if orders:
                        await manager.broadcast("DRIVER_ACTION", {"action": payload.get("action"), "batch": batch.model_dump(mode="json") if batch else None,
                                                                   "orders": websocket.app.state.live_orders.snapshot()["orders"]})
                        driver_id = payload.get("driver_id") or (batch.driver_id if batch else orders[0].driver_id)
                        if driver_id:
                            await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(driver_id))
                        await manager.broadcast("VERDICT_EVALUATION", websocket.app.state.live_orders.verdict_evaluation())
                        await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                    else:
                        await manager.send(websocket, "error", {"message": "No live assignment is available"})
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid DRIVER_ACTION", "details": _validation_details(exc)})
            elif message_type == "DRIVER_TELEMETRY":
                try:
                    telemetry = await websocket.app.state.live_orders.update_telemetry(payload)
                    await manager.broadcast("DRIVER_TELEMETRY", telemetry)
                    await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(telemetry["driver_id"]))
                    await manager.broadcast("VERDICT_EVALUATION", websocket.app.state.live_orders.verdict_evaluation())
                    await manager.broadcast("LIVE_METRICS", websocket.app.state.live_orders.snapshot()["metrics"])
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid DRIVER_TELEMETRY", "details": _validation_details(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
