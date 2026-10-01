# Immich

Self-hosted photo and video backup with search by date, place and faces.

## Key points

- Four containers: the server, a machine-learning service (face and object recognition), PostgreSQL (with vector extensions) and Redis/Valkey.
- Copy `.env.example` to `.env` and choose a database password. Never commit `.env`.
- The compose file is based on the project's official example (the source is credited in its header); image versions are pinned by digest.
- **Operational note:** restarting the server container triggers a full integrity scan of the photo library, which loads a slow disk for about 30 minutes. Avoid restarting it casually.

## Files

- `.env.example`
- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
