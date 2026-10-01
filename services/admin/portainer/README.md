# Portainer

Web UI for inspecting and managing containers (logs, restarts, shells).

## Key points

- Talks to Docker through the socket. Open it over `https://`; the first-run certificate is self-signed, so browsers warn.
- It forces you to create an admin password on first start. Choose a strong one.
- Started originally with `docker run`; the Compose file was reconstructed from the running container.

## Files

- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
