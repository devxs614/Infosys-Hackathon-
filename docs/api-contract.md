# API and WebSocket contract

All REST responses are JSON. `GET /` returns service links. `GET /health` reports `{status, simulation_running, websocket_clients, fallbacks}` without exposing credentials.

| Endpoint | Body | Result |
| --- | --- | --- |
| `POST /demo/start` | none | Starts the asynchronous seeded simulation and returns `{status, state}`. |
| `POST /demo/stop` | none | Stops its loop without losing the current state. |
| `POST /demo/reset` | none | Resets both worlds to the configured seed. |
| `GET /demo/state` | none | Current `SimulationState`. |
| `POST /demo/trigger` | `{"event_type":"TORRENTIAL_RAIN","zone":"Monterrey"}` | Activates a judge event. |
| `POST /demo/judge-event` | Same as trigger | Alias for judge tooling. |
| `POST /route/estimate` | `{"origin":[lat,lon],"destination":[lat,lon]}` | OSRM street geometry, distance and ETA; local fallback when OSRM is unreachable. |
| `WS /ws` | optional `{"type":"ping"}` | Receives state/event messages and answers with `pong`. |

Every WebSocket frame has this envelope:

```json
{"type":"simulation_state","timestamp":1710000000000,"data":{}}
```

Types are `connection`, `hello_response`, `simulation_state`, `driver_update`, `order_update`, `decision`, `telemetry`, `event`, `metrics`, and `error`. Every type is emitted by the current implementation as applicable to a tick or client session. `simulation_state.data` contains `simulation_minute`, `baseline`, `ai_driver`, `orders`, `weather`, `traffic`, `events`, `last_decisions`, and `metrics`. A `decision` frame has `{agent, decision}`, where `decision` includes `decision_type`, `selected_order_ids`, reasoning, estimates, and confidence.

## Rumbo live-order messages

The same central `/ws` connection coordinates any number of Rumbo clients and couriers. The browser keeps its session locally, then announces its public profile (no password is sent):

```json
{
  "type": "REGISTER_USER",
  "data": {
    "id": "client-sofia-k82p",
    "name": "Sofía Garza",
    "email": "sofia@example.com",
    "role": "client"
  }
}
```

For `role: "driver"`, an optional `location: [lat, lon]` makes that courier immediately eligible for proximity assignment. The server broadcasts `USER_REGISTERED`, `DRIVER_ONLINE`, `LIVE_ORDER_STATE`, and `LIVE_METRICS`. `USER_REGISTERED` and `DRIVER_ONLINE` are also accepted as backward-compatible registration aliases.

A client sends a dynamic order directly (or wraps its fields in `data`):

```json
{
  "type": "NEW_ORDER",
  "data": {
    "client_id": "client-sofia-k82p",
    "client_name": "Sofía Garza",
    "restaurant": "Rumbo Kitchen · Centrito",
    "origin": [25.6496, -100.3595],
    "destination": [25.6517, -100.2892],
    "destination_label": "Campus Tec",
    "items": [{"id": "citrus-bowl", "name": "Citrus Bowl", "price": 198, "quantity": 1}]
  }
}
```

Every coordinate is validated to the Monterrey metro area. The Edge server calls OSRM for street geometry when available, computes the delivery fee and ETA, assigns the nearest online courier, and broadcasts `NEW_ORDER`. Nearby unbatched orders are evaluated by Gemini and produce `AI_BATCH_OPTIMIZATION`, `AI_BATCH_SUGGESTION`, and `DRIVER_NOTIFICATION`. The batch payload includes `route`, `individual_distance_km`, `batch_distance_km`, `savings_percent`, `reasoning`, `status`, and `driver_id`.

The courier accepts a route and publishes telemetry with:

```json
{"type":"DRIVER_ACTION","data":{"action":"ACCEPT_ASSIGNMENT","driver_id":"driver-alex-r3m","order_id":"RUM-0001"}}
{"type":"DRIVER_TELEMETRY","data":{"driver_id":"driver-alex-r3m","position":[25.652,-100.31],"bearing":42,"street_name":"Av. Lázaro Cárdenas","speed_kmh":45}}
```

Actions are `ACCEPT_ASSIGNMENT`, `ACCEPT_BATCH`, `ARRIVED_RESTAURANT`, `START_DELIVERY`, and `DELIVERED`; the original demo action names remain accepted. The Raspberry also emits a server-side `DRIVER_TELEMETRY` snapshot twice per second during the accelerated simulation. Clients interpolate those points at display frame rate. Judge traffic events recalculate the visible live recommendation through `/demo/trigger`.
