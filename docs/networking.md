# Hotspot networking

```text
Phone hotspot
  ├── Raspberry Pi: 10.71.42.73:8000
  └── Laptop: Vite dashboard on 192.168.56.1:5173
```

On the Pi, run `hostname -I`. From a laptop connected to the same hotspot, verify reachability:

```bash
ping 10.71.42.73
curl http://10.71.42.73:8000/health
```

`dashboard_client/.env` is configured with `VITE_WS_HOST=10.71.42.73`, `VITE_WS_PORT=8000`, and `VITE_DASHBOARD_HOST=192.168.56.1`. Restart Vite after editing it. The socket is `ws://10.71.42.73:8000/ws`. Do not use `localhost` from the laptop to address the Pi: it would target the laptop itself.
