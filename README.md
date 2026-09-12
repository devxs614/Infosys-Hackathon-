# Rumbo | Edge Logistics OS

**Infosys HackMTY 2026 — Challenge 3: The Courier**

## Rumbo interface

The dashboard is now branded **Rumbo | Edge Logistics OS**. Its single React application uses a dynamic local session and may be opened from any number of laptops backed by the same Raspberry Pi WebSocket:

| Route | Demo account | Purpose |
| --- | --- | --- |
| `/` | Login / Registro | Glassmorphic session flow for any Cliente or Repartidor, plus demo buttons. |
| `/app/client` | Dynamic client | Restaurant, address search / draggable map pin, price and OSRM route preview. |
| `/app/driver` | Dynamic courier | Assignment, navigation HUD and interpolated live telemetry. |
| `/app/dashboard` | Command Center | Apple-style bento operating picture for all active clients, orders and drivers. |

Page and modal transitions use Framer Motion; the UI uses Tailwind CSS, Lucide icons, and a Leaflet map with CartoDB Dark Matter tiles. Routes come from OSRM through the Edge node and fall back gracefully when the Pi is offline. See the dynamic Rumbo protocol in [docs/api-contract.md](docs/api-contract.md#rumbo-live-order-messages).

Courier Edge Decision System is a resilient edge simulation for comparing a reasonable reactive courier against a strategic AI/Gemini courier. It converts a four-hour shift into a three-minute reproducible demo, measures MXN per simulated hour, earnings, distance and late deliveries, and shows the comparison on a laptop dashboard.

It does not fabricate an AI advantage. One seeded `ScenarioStream` produces each order, timestamp, traffic condition, weather condition, surge, and disruption exactly once. Those inputs are copied to independent `BaselineWorld` and `GeminiWorld` instances; only decisions diverge.

## Architecture

```text
GitHub repository
    ├── Raspberry Pi 5: FastAPI + WebSocket + simulation + agents + routing + telemetry
    └── Laptops: React/Vite dashboard, judge controls and visualization

ScenarioStream → BaselineWorld → BaselineAgent
               └→ GeminiWorld   → GeminiAgent → DecisionValidator
                                      ↓
                                 RoutingEngine → Simulation → WebSocket → Dashboard
```

The edge service runs at `0.0.0.0:8000`; the configured dashboard uses `ws://10.71.42.73:8000/ws`. See [the architecture notes](docs/architecture.md) for the component boundaries.

## Repository layout

| Folder | Responsibility |
| --- | --- |
| `edge_server/` | Raspberry-ready FastAPI service, simulation, agents, routing and fallbacks. |
| `dashboard_client/` | React/Vite display and judge controls; no decision logic. |
| `database/` | Optional PostgreSQL/Tiger telemetry schema. |
| `tests/` | Offline unit/API tests; no Internet, Gemini or database required. |
| `scripts/` | Raspberry setup, server, demo and health-check helpers. |
| `docs/` | Architecture, networking, API, collaboration and demo playbooks. |

## Prerequisites

- Python **3.11+** (on Raspberry Pi or local development laptop)
- Node.js **20+** and npm (dashboard laptop)
- A route from the laptop to the configured Raspberry Pi IP (`10.71.42.73`) for a multi-device demo

Gemini, OSRM and Tiger Data are optional. The application starts without credentials and falls back respectively to a strategic deterministic policy, local Haversine routing, and in-memory telemetry.

## Local laptop setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env                   # Windows PowerShell: Copy-Item .env.example .env
```

Start the backend in terminal 1:

```bash
uvicorn edge_server.main:app --host 0.0.0.0 --port 8000
```

Start the dashboard in terminal 2:

```bash
cd dashboard_client
cp .env.example .env                   # Windows PowerShell: Copy-Item .env.example .env
npm install
npm run dev
```

The configured deployment binds Vite to `192.168.56.1:5173` and connects it to the Raspberry at `10.71.42.73:8000`. Browse to `http://192.168.56.1:5173`, press **Start demo**, and use the event buttons.

## Raspberry Pi setup and launch

Clone the same GitHub repository on the Pi, then run:

```bash
cd courier-edge-system
chmod +x scripts/*.sh
./scripts/setup_pi.sh
source .venv/bin/activate
./scripts/run_server.sh
```

Equivalent direct command:

```bash
uvicorn edge_server.main:app --host 0.0.0.0 --port 8000
```

`scripts/health_check.sh` verifies `http://127.0.0.1:8000/health`. `scripts/run_demo.sh` starts the service and requests the demo endpoint.

On the Raspberry Pi, after PostgreSQL and the `courier_edge_db` database are running, initialize the telemetry schema once:

```bash
sudo apt install postgresql-client
./scripts/initialize_database.sh
```

Git does not carry `.env`. Transfer the already-configured ignored `.env` to the Raspberry through your approved secure channel before starting the service; do not add it to a commit.

## Connect laptop dashboard to the Raspberry Pi

Put the Pi and laptop on the same hotspot. On the Pi:

```bash
hostname -I
```

Copy the reported LAN IP into `dashboard_client/.env`:

```dotenv
VITE_WS_HOST=10.71.42.73
VITE_WS_PORT=8000
VITE_DASHBOARD_HOST=192.168.56.1
```

Restart `npm run dev`. From the laptop, verify:

```bash
curl http://10.71.42.73:8000/health
```

The dashboard uses `ws://10.71.42.73:8000/ws`; it does not hardcode `localhost`. Inspect the browser's Network → WS panel to test the WebSocket. After the connection message, it receives `hello_response`; after **Start demo**, it receives `simulation_state`, `decision`, `metrics`, and event messages.

## Configuration and secrets

Copy `.env.example` to `.env`. Important safe defaults are:

```dotenv
HOST=0.0.0.0
PORT=8000
SHIFT_MINUTES=240
DEMO_SECONDS=180
TICK_MS=500
USE_OSRM=true
USE_TIGER=true
USE_GEMINI=true
SCENARIO_SEED=42
```

Set `GEMINI_API_KEY` and `TIGER_DB_URL` only in your local `.env`; these values are ignored by Git and never sent to the frontend. Set `GEMINI_MODEL=auto` to discover a compatible, currently available Gemini text model at runtime rather than pinning an aging version. If the API is unavailable, the deterministic strategic fallback runs instead.

## Run tests

Tests do not depend on Internet or keys:

```bash
source .venv/bin/activate
pytest -q
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q
```

## GitHub and Live Share

Suggested long-lived branch responsibilities:

```text
main
├── backend/raspberry
├── frontend/dashboard
├── ai/gemini
└── qa/demo
```

First commit and push after creating a GitHub repository:

```bash
git init
git add .
git commit -m "Initial Courier Edge Decision System"
git branch -M main
git remote add origin https://github.com/OWNER/courier-edge-system.git
git push -u origin main
```

For everyday work, `git pull origin main`, create a focused branch, commit, push, and open a pull request. VS Code Live Share can pair a teammate into the current editor but does not replace branches, reviews, or commits. More detail is in [docs/development.md](docs/development.md).

## API, events and demo

Useful controls are `POST /demo/start`, `/demo/stop`, `/demo/reset`, `/demo/trigger`, `/demo/judge-event`, plus `GET /demo/state`. Available event types are `EXTREME_HEAT`, `TORRENTIAL_RAIN`, `GONZALITOS_FLOOD`, `SAN_PEDRO_SURGE`, and `ROAD_CLOSURE`.

For the full request/response contract read [docs/api-contract.md](docs/api-contract.md). Use the three-minute presentation sequence in [docs/demo.md](docs/demo.md). In a live pitch, report the metrics produced by the current seeded run—not a prewritten percentage.

## Next phase

The scaffold is ready for real restaurant datasets, calibrated delivery economics, richer geometry, authenticated Tiger deployment, empirical Gemini prompt evaluation, and multiple city profiles. Add these behind the existing interfaces so the offline demo remains stable.

## Troubleshooting

- **Dashboard is disconnected:** verify that the laptop can reach the Pi and `curl http://10.71.42.73:8000/health` works, then restart Vite after changing `dashboard_client/.env`.
- **No Gemini/Tiger/OSRM access:** expected in offline mode. Check `/health`; the fallback flags should be true and the simulation should still run.
- **Port already in use:** change `PORT` and the frontend `VITE_WS_PORT` together.
- **Map tiles blank:** Internet may be unavailable. The Leaflet map can be empty while controls, metrics and local WebSocket continue working.
- **Python package error:** activate the project venv and rerun `python -m pip install -r requirements.txt`.
