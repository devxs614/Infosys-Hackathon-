# Hotspot networking

```text
Phone hotspot
  ├── Raspberry Pi: 192.168.x.x:8765
  └── Laptop: Vite dashboard on localhost:5173
```

On the Pi, run `hostname -I`. From a laptop connected to the same hotspot, verify reachability:

```bash
ping RASPBERRY_IP
curl http://RASPBERRY_IP:8765/health
```

Copy `dashboard_client/.env.example` to `.env`, set `VITE_WS_HOST=RASPBERRY_IP` and `VITE_WS_PORT=8765`, then restart Vite. The socket is `ws://RASPBERRY_IP:8765/ws`. Do not use `localhost` from a laptop to address the Pi: that would target the laptop itself. When both pieces run on one development laptop, leave `VITE_WS_HOST` blank so the browser hostname is used dynamically.

