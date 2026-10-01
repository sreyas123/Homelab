# Monitoring and alerting

Self-monitoring is the part of this project I put the most design effort into. It has three independent
layers so that one failing does not blind the others.

| Layer | Watches | Mechanism | Notifies via |
|---|---|---|---|
| **server-watcher** | every container (running and healthy), root disk %, memory % | Python loop, polls the Docker API every 60 s | ntfy push + lantern |
| **disk-watch** | kernel disk errors, read-only remount, sustained slow reads | shell script from cron every 2 min | ntfy push only |
| **smartd** | SMART attributes (reallocated, pending, uncorrectable sectors), self-tests | systemd service, scheduled tests | ntfy push only |
| **light-alerts** | the alert stream above | Python, subscribes to ntfy | lantern: red / green |

## server-watcher

[`watch.py`](../services/monitoring/server-watcher/watch.py) is about 200 lines of standard-library Python.

- Talks to the Docker Engine API over the (read-only mounted) socket; no third-party dependencies.
- **Alerts on transitions, not on state.** It stores the last known state per container in a volume. A
  container going `running -> unhealthy` produces one `DOWN:` message and, when it returns,
  one `RECOVERED:` message. This avoids an alert every minute for the same problem.
- Also reports a new container appearing and a container being removed.
- Disk thresholds: warning at 85%, critical at 95%. Memory warning at 90%. All configurable through
  environment variables.
- Message titles follow a small contract used by the lantern bridge:
  `DOWN: <name>`, `RECOVERED: <name>`, `DISK ALERT: ...`, `MEMORY ALERT: ...`.

## light-alerts (the status light)

[`alert_light.py`](../services/smart-home/light-alerts/alert_light.py) subscribes to the same ntfy topic.

1. A new `DOWN:`, `DISK ALERT` or `MEMORY ALERT` adds the problem to an in-memory set. If it is new, the
   lantern flashes red three times and then stays solid red.
2. A matching `RECOVERED:` message removes it from the set.
3. When the set becomes empty, the lantern shows green for 20 seconds and returns to warm white.

Details worth noting:

- It **keeps a set of open problems** rather than reacting to single messages, so two overlapping
  incidents do not turn the lantern green early.
- It writes a flag file while any problem is open. The lantern's software light effects (rainbow, candle
  and so on, in [`lantern_effects.py`](../services/smart-home/home-assistant/config/lantern_effects.py))
  check that file and stop themselves so they can never paint over a red alert.
- The lantern is controlled over its documented UDP LAN API (JSON on port 4003), so the signal still works
  during an internet outage.

## disk-watch and smartd (drive health)

The server has a single hard drive that is slow under load (see the [incident write-up](incident-slow-disk.md)),
so drive health gets its own layer.

[`disk-watch.sh`](../services/monitoring/disk-watch/disk-watch.sh) looks for three things:

1. **New kernel disk errors** (`I/O error`, `Unrecovered read error`, ATA resets, ext4 errors).
2. **Root filesystem remounted read-only**, which means the kernel hit a serious error.
3. **Sustained slow reads**: average read latency above 250 ms with the disk more than 90% busy, for about
   16 minutes. It computes this from deltas of `/proc/diskstats` between runs, and sends a "back to normal"
   message when it clears.

[`install-smart-alerts.sh`](../services/monitoring/disk-watch/install-smart-alerts.sh) configures `smartd`
to run all checks, schedule a short self-test daily and a long self-test weekly, watch the raw values of the
reallocated, uncorrectable, pending and offline-uncorrectable attributes, and post warnings to ntfy through a
`run.d` hook.

### Why drive alerts do not control the lantern

The titles used by disk-watch and smartd deliberately avoid the prefixes the lantern bridge reacts to.
A container problem recovers, so "red then green" is meaningful. A drive error never recovers: if it
turned the lantern red it would stay red permanently and stop carrying information. Drive warnings
therefore go to the phone only.

## Testing the chain

```bash
docker stop <some-container>     # phone buzzes, lantern flashes red then holds red
docker start <some-container>    # RECOVERED message, lantern green 20 s, then warm white
```

## Possible improvements

- Persist the lantern bridge's open-problem set so a restart does not forget active alerts.
- Add Prometheus and Grafana for history and trends; the current setup answers "is it broken now?" but not
  "how has it behaved this month?".
- Alert on backup freshness once off-site backups exist.
