# Security notes

This is a home server, so the threat model is modest: stop strangers on the internet, limit what a
compromised device on the network could reach, and keep secrets out of version control. This page records
what I did, how I **verified** it, and what is still open.

## Principles

1. **Nothing is exposed to the internet.** No router port forwarding. Remote access is through Tailscale only.
2. **Verify, don't assume.** Configuration was checked from the outside, not just reviewed.
3. **Secrets stay out of the repo.** `.env` files are git-ignored; each folder ships an `.env.example`.
4. **Write down the gaps.** Known weaknesses are listed below instead of hidden.

## Remote access: Tailscale

- WireGuard-based mesh VPN; only devices signed in to my account can reach the server.
- No inbound ports are opened on the router, so there is no public attack surface for the apps.
- The server also advertises the home subnet to the tailnet (a *subnet router*), so remote devices can use
  LAN addresses. **Trade-off:** if one of my Tailscale devices or the account were compromised, an attacker
  could reach the whole home network, not just the server. Recommended mitigations: two-factor
  authentication on the identity account, removing stale devices from the tailnet, and (optionally) access
  control lists limiting which devices can reach which ports.

## How exposure was verified

1. **Router review:** no virtual servers (port forwards), no DMZ, remote management disabled, and the UPnP
   mapping table contained only Tailscale's own encrypted UDP mappings (queried over UPnP/SOAP from the server).
2. **External port probe:** I connected to the home's public IP from a different network (a remote vantage
   point with a different public address) on every port the services use, plus SSH, SMB and RDP. Controls
   confirmed the method worked (known-open ports reported open, random closed ports reported closed).
   **Result: none of the service ports were reachable.**
3. **IPv6:** the server had no public IPv6 address, so there was no second path in.
4. **Tailscale features:** `serve` and `funnel` (which can publish services publicly) were not configured.

A few ports on the public address did answer and reset the connection. They were not forwarded to the
server (Virtual Servers was empty); the most likely explanation is the internet provider's equipment, which
I cannot inspect.

## Authentication on the local network

Anyone on the home Wi-Fi can reach the server's ports, so each service's own login matters. I checked which
services demand a login without authenticating:

| Requires login | No login on the LAN |
|---|---|
| Home Assistant, Immich, Navidrome | Homepage dashboard and the live status dashboard (read-only status pages) |
| Jellyfin (sign-in screen; only the public user list is visible) | |
| Portainer (forces an admin password on first run; not probed) | |

The live status dashboard is deliberately read-only and has no secrets to leak: it exposes container names,
health and resource numbers, nothing else. Its container runs with a read-only filesystem, all Linux capabilities
dropped, `no-new-privileges`, and CPU and memory limits, and it only mounts the Docker socket, `/sys` and the host
root as read-only.

## Secrets handling

- Compose files reference `${VARIABLES}`; real values live in git-ignored `.env` files.
- The notification topic works like a password (anyone who knows it can read the alerts), so it is treated as
  a secret and stored only in `.env`.
- Before publishing this repository, all files were scanned for credentials, tokens, private addresses,
  e-mail addresses and device identifiers, and the git history was reduced to a single clean commit.

## Known gaps and next steps

| Gap | Planned fix |
|---|---|
| Visitors on the main Wi-Fi can reach the server | Use the router's guest network with local-network access disabled |
| Homepage and the status dashboard have no login | Put them behind Tailscale only or add a reverse proxy with authentication |
| Subnet routing widens Tailscale's reach | Tailscale ACLs, or advertise only the server instead of the whole subnet |
| An unused web server (Apache) is installed on the host | Disable and remove it |
| Single drive, no off-site backup | SSD upgrade and an encrypted off-site backup of the photo library |
