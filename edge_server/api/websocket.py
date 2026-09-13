"""Authenticated central WebSocket gateway for all Rumbo laptops."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

router = APIRouter()


def _validation_details(error: ValidationError) -> list[dict[str, object]]:
    return [{"loc": list(item["loc"]), "message": item["msg"], "type": item["type"]} for item in error.errors()]


async def _identity(websocket: WebSocket, payload: dict) -> dict | None:
    user_id = await websocket.app.state.connections.user_id_for(websocket)
    return websocket.app.state.auth_store.authenticate_session(user_id, payload.get("session_token")) if user_id else None


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
                continue

            if message_type in {"REGISTER_USER", "USER_REGISTERED", "DRIVER_ONLINE"}:
                try:
                    identity = websocket.app.state.auth_store.authenticate_session(
                        payload.get("user_id") or payload.get("id"), payload.get("session_token"),
                    )
                    if not identity:
                        await manager.send(websocket, "error", {"message": "Authenticate with /api/auth before opening the live session"})
                        continue
                    await manager.bind_user(websocket, identity["id"])
                    registration = await websocket.app.state.live_orders.register_user({**identity, "location": payload.get("location")})
                    await manager.broadcast("USER_REGISTERED", registration)
                    if registration.get("driver"):
                        await manager.broadcast("DRIVER_ONLINE", {"driver": registration["driver"], "metrics": registration["metrics"]})
                        for order_id in registration.get("dispatched_order_ids", []):
                            dispatch = websocket.app.state.live_orders.order_dispatch_payload(websocket.app.state.live_orders.orders[order_id])
                            if dispatch:
                                await manager.send_to_user(registration["driver"]["id"], "ORDER_DISPATCHED", dispatch)
                        await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(registration["driver"]["id"]))
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid REGISTER_USER", "details": _validation_details(exc)})
                continue

            identity = await _identity(websocket, payload)
            if not identity:
                await manager.send(websocket, "error", {"message": "Authenticate with /api/auth before using the live session"})
                continue

            if message_type == "NEW_ORDER":
                try:
                    if identity["role"] != "client" or payload.get("client_id") != identity["id"]:
                        await manager.send(websocket, "error", {"message": "Only the authenticated customer can create this order"})
                        continue
                    order, batch = await websocket.app.state.live_orders.create_order({**payload, "client_id": identity["id"], "client_name": identity["name"]})
                    await manager.broadcast("NEW_ORDER", {"order": order.model_dump(mode="json")})
                    dispatched = [order] if not batch else [websocket.app.state.live_orders.orders[order_id] for order_id in batch.order_ids]
                    for candidate in dispatched:
                        dispatch = websocket.app.state.live_orders.order_dispatch_payload(candidate)
                        if dispatch:
                            await manager.send_to_user(candidate.driver_id, "ORDER_DISPATCHED", dispatch)
                    if not any(candidate.driver_id for candidate in dispatched):
                        await manager.broadcast("NO_DRIVERS_AVAILABLE", {"status": "NO_DRIVERS_AVAILABLE", "order": order.model_dump(mode="json"), "message": "No hay repartidores disponibles en este momento"})
                    if batch:
                        batch_data = batch.model_dump(mode="json")
                        await manager.broadcast("AI_BATCH_SUGGESTION", batch_data)
                        await manager.broadcast("AI_BATCH_OPTIMIZATION", batch_data)
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                except ValidationError as exc:
                    await manager.send(websocket, "error", {"message": "Invalid NEW_ORDER", "details": _validation_details(exc)})
                except ValueError as exc:
                    await manager.send(websocket, "error", {"message": str(exc)})

            elif message_type == "CANCEL_ORDER":
                try:
                    if identity["role"] != "client" or payload.get("client_id") != identity["id"]:
                        await manager.send(websocket, "error", {"message": "Only the authenticated customer can cancel this order"})
                        continue
                    order, batch = await websocket.app.state.live_orders.cancel_order(payload)
                    event = {"order": order.model_dump(mode="json"), "batch": batch.model_dump(mode="json") if batch else None, "driver_id": order.driver_id}
                    await manager.broadcast("ORDER_CANCELLED", event)
                    if order.driver_id:
                        await manager.send_to_user(order.driver_id, "DRIVER_NOTIFICATION", {"title": "Pedido cancelado por el cliente", "driver_id": order.driver_id, "order": event["order"], "message": f"{order.client_name} canceló el pedido {order.id}."})
                        await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(order.driver_id))
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                except (ValidationError, ValueError) as exc:
                    details = _validation_details(exc) if isinstance(exc, ValidationError) else None
                    await manager.send(websocket, "error", {"message": "Invalid CANCEL_ORDER" if details else str(exc), **({"details": details} if details else {})})

            elif message_type == "DRIVER_ACTION":
                try:
                    if identity["role"] != "driver" or payload.get("driver_id") != identity["id"]:
                        await manager.send(websocket, "error", {"message": "Only the authenticated courier can update this assignment"})
                        continue
                    batch, orders = await websocket.app.state.live_orders.apply_driver_action(payload)
                    if not orders:
                        await manager.send(websocket, "error", {"message": "No live assignment is available"})
                        continue
                    await manager.broadcast("DRIVER_ACTION", {"action": payload.get("action"), "batch": batch.model_dump(mode="json") if batch else None, "orders": websocket.app.state.live_orders.snapshot()["orders"]})
                    for order in orders:
                        match = websocket.app.state.live_orders.order_match_payload(order)
                        if match:
                            await manager.broadcast("ORDER_MATCHED", match)
                    await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(identity["id"]))
                    await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
                except (ValidationError, ValueError) as exc:
                    details = _validation_details(exc) if isinstance(exc, ValidationError) else None
                    await manager.send(websocket, "error", {"message": "Invalid DRIVER_ACTION" if details else str(exc), **({"details": details} if details else {})})

            elif message_type == "DRIVER_TELEMETRY":
                try:
                    if identity["role"] != "driver" or payload.get("driver_id") != identity["id"]:
                        await manager.send(websocket, "error", {"message": "Only the authenticated courier can send telemetry"})
                        continue
                    telemetry = await websocket.app.state.live_orders.update_telemetry(payload)
                    await manager.broadcast("DRIVER_TELEMETRY", telemetry)
                    await manager.broadcast("DRIVER_FINANCIAL_UPDATE", websocket.app.state.live_orders.driver_financial_update(telemetry["driver_id"]))
                    await manager.broadcast("LIVE_METRICS", websocket.app.state.live_orders.snapshot()["metrics"])
                except (ValidationError, ValueError) as exc:
                    details = _validation_details(exc) if isinstance(exc, ValidationError) else None
                    await manager.send(websocket, "error", {"message": "Invalid DRIVER_TELEMETRY" if details else str(exc), **({"details": details} if details else {})})
    except WebSocketDisconnect:
        pass
    finally:
        user_id, still_connected = await manager.disconnect(websocket)
        if user_id and not still_connected:
            driver = await websocket.app.state.live_orders.set_driver_online(user_id, False)
            if driver:
                await manager.broadcast("DRIVER_OFFLINE", {"driver": driver, "metrics": websocket.app.state.live_orders.snapshot()["metrics"]})
                for order in await websocket.app.state.live_orders.redispatch_pending_orders():
                    dispatch = websocket.app.state.live_orders.order_dispatch_payload(order)
                    if dispatch:
                        await manager.send_to_user(order.driver_id, "ORDER_DISPATCHED", dispatch)
                await manager.broadcast("LIVE_ORDER_STATE", websocket.app.state.live_orders.snapshot())
