# Rumbo · dynamic multi-laptop demo runbook

1. Start the FastAPI service on the Raspberry Pi at `0.0.0.0:8000` and start the dashboard on each laptop.
2. On Laptop A, create any **Cliente** profile and choose a restaurant plus a delivery pin in Monterrey.
3. On Laptop B, create another **Cliente** profile and choose a nearby delivery pin. Both profiles are independent and persist only in their own browser.
4. On Laptop C, create a **Repartidor** profile. It becomes online immediately; the closest available courier is matched automatically.
5. Open `/app/dashboard` on Laptop D for the aggregate Command Center. It shows online drivers plus `PENDING`, `MATCHED`, `IN_TRANSIT`, and `DELIVERED` orders.
6. Accept the assignment in the Driver HUD. The courier advances along the OSRM street geometry under the 120× time warp; every screen receives the same interpolated telemetry.
7. Trigger rain, Gonzalitos flood, or San Pedro congestion from the Command Center to show the Edge recalculation.

If the Pi does not have Internet access, OSRM and map tiles will gracefully fall back: routing still produces an ETA and the WebSocket workflow remains operational.

## Optional seeded baseline comparison

1. Confirm `/health` from a laptop and that the dashboard says **Raspberry Connected**.
2. Press **Reset**, explain that seed 42 feeds exactly the same orders, weather and events to both drivers.
3. Press **Start demo** and point out the two live metric cards and the AI decision panel.
4. Trigger **San Pedro surge**; explain that the strategic policy can evaluate demand and batches while the baseline remains reactive.
5. Trigger **Torrential rain**, then **Gonzalitos flood** or **Road closure**. Show the active event panel and the route-risk response.
6. End by showing total earnings, distance, late orders and MXN/simulated-hour. The comparison is computed live; do not promise an improvement before the run produces it.

Run the same seed again for a reproducible conversation with judges. Do not hardcode outcomes: the dashboard derives every percentage from the backend's current state.
