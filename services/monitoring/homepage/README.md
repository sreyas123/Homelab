# Homepage

Phone-friendly dashboard with a tile per service and live container status.

## Key points

- Tiles are defined in `config/services.yaml`; status dots come from the Docker socket (read-only) and HTTP checks.
- The top bar shows time, CPU, temperature, memory, uptime and disk usage (`config/widgets.yaml`).
- `custom.css` and `custom.js` make it phone-first (two tiles per row, compact cards, one group collapsed by default).
- Replace the `<TAILSCALE_IP>` and example `192.168.0.x` addresses with your own (bracketed notes mark the spot).
- The dashboard has no login of its own, so keep it on the LAN or behind Tailscale ([security notes](../../../docs/security.md)).

## Files

- `config`
- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
