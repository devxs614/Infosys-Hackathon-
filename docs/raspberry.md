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

The server listens on `0.0.0.0:8000`; its configured address is `10.71.42.73`. Confirm it with `hostname -I`. The dashboard is configured to use this address. A 4 GB Pi can use Gemini and Tiger when they are reachable; the local fallbacks keep the demo safe when either service is unavailable.
