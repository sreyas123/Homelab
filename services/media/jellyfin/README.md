# Jellyfin

Media server for my own library of video and music.

## Key points

- Reads three bind-mounted folders (movies, tv, music) and builds a browsable library with metadata.
- Config and cache are separate bind mounts so the cache can be deleted safely.
- Started originally with `docker run`; the Compose file was reconstructed from the running container, so the recipe is now reproducible.
- The built-in health check has a 30 s timeout, which a saturated disk can exceed (see the [incident write-up](../../../docs/incident-slow-disk.md)).

## Files

- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
