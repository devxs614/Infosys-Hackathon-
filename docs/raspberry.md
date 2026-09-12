# Raspberry Pi edge node

The Raspberry Pi clones the entire repository because GitHub is the shared source of truth, but it executes only the Python backend. It does not need to run Vite in the live demo.

```bash
git clone <YOUR_REPOSITORY_URL> courier-edge-system
cd courier-edge-system
chmod +x scripts/*.sh
./scripts/setup_pi.sh
source .venv/bin/activate
./scripts/run_server.sh
```

The server listens on `0.0.0.0:8765`. Get its LAN address with `hostname -I`; give that address to dashboard users as `VITE_WS_HOST`. A 4 GB Pi should leave OSRM, Gemini and Tiger disabled unless their network connection is stable—the local fallbacks are the normal demo-safe path.

