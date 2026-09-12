# Architecture

`edge_server` is the Raspberry Pi edge node. It owns the FastAPI server, WebSocket hub, seeded scenario stream, two independent driver worlds, agents, routing and telemetry. `dashboard_client` is deliberately a thin React client: it renders state and sends judge commands; it never computes courier decisions.

```text
ScenarioStream (seeded once)
        ├── BaselineWorld → BaselineAgent
        └── GeminiWorld   → GeminiAgent → DecisionValidator
                                     \       /
                                      RoutingEngine
                                           ↓
                               Simulation + Telemetry
                                           ↓
                                  WebSocket → Dashboard
```

The stream creates orders and automatic disruptions once, then deep-copies each item into both worlds. Consequently a driver decision can change only that driver's world and never the input scenario. The Gemini adapter has an offline deterministic strategic policy; its interface can use the `google-genai` SDK when an API key and model are configured. Routing similarly prefers OSRM but has a Haversine-based fallback. Tiger/PostgreSQL is optional and telemetry always remains in memory.

The API binds to `0.0.0.0:8000`, so local WebSockets work independently of Internet access. The configured dashboard connects to `ws://10.71.42.73:8000/ws`. External calls use a short timeout and are never a prerequisite for the simulation.
