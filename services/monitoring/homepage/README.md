# Homepage

Phone-friendly dashboard with a tile per service and live container status.

## Key points

- Tiles are defined in `config/services.yaml`; status dots come from the Docker socket (read-only) and HTTP checks.
- **Frosted-glass theme:** `config/custom.css` styles tiles and the stats bar as translucent glass (backdrop blur, edge highlights, soft coloured light), uses two columns in portrait and four or more in landscape and on wide screens, and lowers the blur on phones for smoother scrolling.
- **Live numbers on every tile:** each tile has a `customapi` widget that reads CPU and memory from the [status dashboard](../status-dashboard)'s API, and a "Live" tile at the top shows the server's overall health. No API keys are needed.
- The top bar shows time, CPU, temperature, memory, uptime and disk usage (`config/widgets.yaml`).
- `custom.js` collapses the Background group by default.
- Replace the `<TAILSCALE_IP>` and example `192.168.0.x` addresses with your own (bracketed notes mark the spot).
- The dashboard has no login of its own, so keep it on the LAN or behind Tailscale ([security notes](../../../docs/security.md)).

## Files

- `config`
- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
