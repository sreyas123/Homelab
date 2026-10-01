# Troubleshooting

Start with *which service* is affected; the phone alert names it (for example `DOWN: jellyfin`).

## The lantern is red
At least one problem is open. Open the ntfy app: the latest messages name the service. Check
`docker ps` for `unhealthy` or `Restarting`. The lantern turns green for 20 seconds, then warm white, when every
problem has recovered. Drive-health warnings do **not** affect the lantern (see
[monitoring and alerting](monitoring-and-alerting.md)).

## Several services are unhealthy at the same time
This usually means a shared resource, not several bugs. See the
[incident write-up](incident-slow-disk.md): on this server it was the hard drive saturating.

```bash
head -1 /proc/pressure/io            # sustained values above ~30% mean I/O stalls
cat /proc/loadavg
sudo smartctl -H -A /dev/sda         # drive health
docker stats --no-stream             # per-container load
```

Do not restart the photo service as a first reaction: it starts a half-hour scan of every photo.

## A service says `unhealthy` but its page opens
Health checks have timeouts (10-30 s). A busy disk can exceed them. Check the I/O pressure above before changing the service.

## Home Assistant cannot find the lights
- Discovery is unreliable when the server is on Wi-Fi. Add the devices by IP address.
- Govee: **LAN Control** must be enabled in the Govee app.
- Bluetooth "failed to stop scanner" log lines are harmless.

## Colours on the bulb look washed out
The bulb's white LED was left on. Use the **Bedroom Lamp Fixed** light, which always sets white to 0 for colours.

## The lantern only does on/off
The built-in integration does not support this model. Use the **Desk Lantern** template light defined in
`configuration.yaml`.

## Lantern effects stop or do not start
Effects run as a background process and stop on purpose when you pick a colour, brightness or off, or when a
server alert is active (the flag file `light-alerts/shared/alert` exists). Delete a stale flag file if needed.

## Home Assistant will not start after a config edit
```bash
docker exec homeassistant python3 -m homeassistant --script check_config -c /config
```
Keep a backup copy of `configuration.yaml` before editing.

## The server disappears from the network
- Did the laptop suspend? Check the lid-close setting.
- Is Wi-Fi connected? Try the Tailscale address if the LAN address fails.

## The live dashboard says "Offline", or tiles on the start page show a dash
The status dashboard container is not reachable. Check `docker ps` for `status-dashboard` and `curl http://localhost:3002/healthz`.
The start page tiles read from `http://<server>:3002/api/...`, so fix the address in `services.yaml` if it differs.
A container that is not listed in `services.json` still appears (under "Other") using its Docker name.

## Reading logs
```bash
docker logs --tail 50 <container>
docker logs -f <container>
docker inspect <container> --format '{{.State.Health.Status}}'
```
