# Setup guide

How to reproduce this setup on a fresh machine. Each service is independent, so you can set up only the parts you want.

## Requirements

- A Linux machine that can stay on (8 GB RAM is comfortable; **an SSD is strongly recommended**).
- Docker Engine and the Compose plugin.
- A [Tailscale](https://tailscale.com) account (optional, for remote access).
- The free **ntfy** app on your phone (for alerts).

## 1. Install Docker

Follow <https://docs.docker.com/engine/install/> for your distribution, then:

```bash
sudo usermod -aG docker $USER     # log out and back in
docker run hello-world
```

## 2. Get the repository and create folders

```bash
git clone https://github.com/<you>/homelab.git
cd homelab
mkdir -p ~/server/media/{movies,tv,music,photos} ~/docker
```

Compose files use `${HOME}`, so they work for any user. Search for `(Put` to find every value you need to
change (time zone, addresses, topic names).

## 3. Start the services

The pattern is the same for each folder:

```bash
cd services/<category>/<service>
cp .env.example .env          # only if the folder has one; fill it in
docker compose up -d
docker compose logs -f
```

| Order | Service | After it starts |
|---|---|---|
| 1 | `media/jellyfin` | Create the admin user; add libraries pointing at `/media/movies`, `/media/tv`, `/media/music` |
| 2 | `media/navidrome` | Create the admin user |
| 3 | `media/immich` | Choose a database password in `.env`; create the admin user; install the phone app |
| 4 | `admin/portainer` | Open `https://<server>:9443` and set an admin password |
| 5 | `monitoring/status-dashboard` | Copy `services.example.json` to `services.json` and edit the names; `docker compose up -d --build`; open port 3002 |
| 6 | `monitoring/homepage` | Edit `config/services.yaml` with your own addresses (its tiles read live numbers from the status dashboard) |

## 4. Smart home

1. `cd services/smart-home/home-assistant && docker compose up -d`; create the Home Assistant account.
2. Copy the files from this repo's `config/` folder into the `config` folder Docker created (owned by
   root, so use `sudo`): `configuration.yaml`, `govee_lantern.py`, `lantern_effects.py` and the empty starter
   files (`automations.yaml`, `scripts.yaml`, `scenes.yaml`, `themes/`). Put your lantern's IP address in the
   two `.py` files, then restart Home Assistant.
3. Add the lights by IP address (Settings, Devices and Services, Add Integration). Discovery often does not
   work when the server is on Wi-Fi. For the Govee lantern, enable **LAN Control** in its app first.
4. Hide the plain WiZ lamp entity and use **Bedroom Lamp Fixed**.

## 5. Monitoring and alerts

1. Pick a long random **ntfy topic** and subscribe to it in the ntfy app.
2. Put it in `.env` for both `monitoring/server-watcher` and `smart-home/light-alerts`.
3. Start them: `docker compose up -d --build` in each folder.
4. **Drive health (optional):** `sudo apt install smartmontools`, then
   `sudo bash services/monitoring/disk-watch/install-smart-alerts.sh` and add this cron entry with `crontab -e`:
   `*/2 * * * * /home/YOUR_USER/server/disk-watch/disk-watch.sh`
5. **Test it:** `docker stop <container>` should produce a phone alert and a red lantern; `docker start` should
   produce a recovery message and a green lantern.

## 6. Remote access

Install Tailscale, sign in, and use the server's Tailscale address from your other devices. Do **not**
forward ports on your router.

## Keeping it healthy

- Update a service: `docker compose pull && docker compose up -d` in its folder.
- Do not restart the photo service needlessly: it re-checks every photo and loads the disk for ~30 minutes.
- Keep an off-site copy of irreplaceable data. This repository holds configuration, not data.
- If the machine is a laptop, disable suspend on lid close (`HandleLidSwitch=ignore` in `/etc/systemd/logind.conf`).
