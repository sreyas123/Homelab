# Navidrome

Lightweight music streaming server, compatible with the Subsonic API so many phone apps work with it.

## Key points

- Rescans the music folder every hour (`ND_SCANSCHEDULE`).
- The music folder is mounted **read-only**, so the service cannot modify the library.
- Set the music path in `docker-compose.yml` to wherever your music lives.

## Files

- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
