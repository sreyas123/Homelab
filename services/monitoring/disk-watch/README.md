# disk-watch and smartd (custom)

Early warning for a degrading hard drive.

## Key points

- `disk-watch.sh` runs from cron every 2 minutes and detects: new kernel disk errors, root filesystem remounted read-only, and sustained slow reads (average latency above 250 ms with the disk over 90% busy for about 16 minutes), computed from `/proc/diskstats` deltas.
- `install-smart-alerts.sh` configures `smartd`: full checks, a short self-test daily, a long self-test weekly, alerts on changes to the reallocated, uncorrectable, pending and offline-uncorrectable attributes, and an ntfy hook. Run it with `sudo`.
- Cron entry: `*/2 * * * * /home/YOUR_USER/server/disk-watch/disk-watch.sh` (adjust the path to where you keep the script).
- Alert titles deliberately avoid the prefixes the lantern bridge reacts to, so drive warnings reach the phone without leaving the lantern permanently red.
- Background: [incident write-up](../../../docs/incident-slow-disk.md).

## Files

- `disk-watch.sh`
- `install-smart-alerts.sh`

Secrets and personal values are not stored here; see `.env.example` where present.
