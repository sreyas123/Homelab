# light-alerts (custom)

Small Python service that turns the lantern into a server status light.

## Key points

- Subscribes to the ntfy alert stream and keeps a **set of open problems**.
- New problem: flash red three times, then solid red. All recovered: green for 20 seconds, then warm white.
- Writes a flag file (`shared/alert`) while a problem is open so the software light effects stop themselves.
- Talks to the lantern over its UDP LAN API on port 4003, so it works without internet.
- Configuration: `NTFY_TOPIC` (in `.env`) and `LANTERN_IP` (see the bracketed notes).
- Design details: [monitoring and alerting](../../../docs/monitoring-and-alerting.md).

## Files

- `.env.example`
- `alert_light.py`
- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
