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
| `WS /ws` | optional `{"type":"ping"}` | Receives state/event messages and answers with `pong`. |

Every WebSocket frame has this envelope:

```json
{"type":"simulation_state","timestamp":1710000000000,"data":{}}
```

Types are `connection`, `hello_response`, `simulation_state`, `driver_update`, `order_update`, `decision`, `telemetry`, `event`, `metrics`, and `error`. Every type is emitted by the current implementation as applicable to a tick or client session. `simulation_state.data` contains `simulation_minute`, `baseline`, `ai_driver`, `orders`, `weather`, `traffic`, `events`, `last_decisions`, and `metrics`. A `decision` frame has `{agent, decision}`, where `decision` includes `decision_type`, `selected_order_ids`, reasoning, estimates, and confidence.
