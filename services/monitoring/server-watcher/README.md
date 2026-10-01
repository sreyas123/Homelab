# server-watcher (custom)

Watchdog that checks every container, the root disk and memory once a minute and pushes alerts through ntfy.

## Key points

- Standard-library Python (`watch.py`, about 200 lines) on a small Alpine image; no third-party dependencies.
- Reads container state from the Docker socket (mounted read-only) and disk and memory from the host's `/proc` and filesystem (mounted read-only).
- Alerts on **state changes only**: one `DOWN:` message and one `RECOVERED:` message per incident. State is kept in a named volume.
- Thresholds are environment variables: `DISK_WARN_PCT` (85), `DISK_CRIT_PCT` (95), `MEM_WARN_PCT` (90), `POLL_SECONDS` (60).
- Set `NTFY_TOPIC` in `.env`. Treat the topic like a password: anyone who knows it can read the alerts.

## Files

- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `watch.py`

Secrets and personal values are not stored here; see `.env.example` where present.
