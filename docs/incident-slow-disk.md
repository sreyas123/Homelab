# Incident write-up: container health checks failing across the board

*Blameless post-mortem of a real incident on this server.*

## Summary

Several unrelated containers became `unhealthy` within minutes of each other, the watchdog alerted, and the
status lantern turned red. Nothing was actually broken: the server's single hard drive was saturated
and every read took far too long, so health checks timed out. The system recovered on its own once the
heaviest background job finished. The follow-up was to measure the drive properly, add drive-level alerting
and remove one avoidable source of disk writes.

## Impact

- Media server, photo service and a couple of internal services were slow or unreachable for roughly
  30 minutes.
- No data loss.

## Timeline (condensed)

1. Watchdog alerts: multiple containers `unhealthy`; lantern goes red.
2. `docker ps` showed the containers *running* with failing health checks, not crashed.
3. `top` showed an idle CPU but about 34% I/O wait and a high load average for an 8-thread machine.
4. `/proc/pressure/io` showed pressure above 65% over 5 minutes: processes were stalled on disk.
5. A short per-process I/O sample (reading `/proc/<pid>/io` twice, 5 s apart) showed *low* throughput yet
   blocked processes: a database write had been stuck in uninterruptible sleep (`D` state) for ~19 minutes.
   Low throughput with high latency points to a slow device, not a busy one.
6. `/proc/diskstats` showed the disk about 97% busy with read latencies between 60 and 200 ms.
7. Kernel log had no disk errors. SMART overall status was `PASSED`.
8. The alerts cleared on their own as the background job finished.

## Root cause

The drive is a 5400 rpm laptop hard drive using shingled magnetic recording (SMR), which handles
concurrent random I/O poorly. Several heavy jobs overlapped:

- the photo service's integrity scan (reads every stored photo),
- its scheduled database backup,
- routine media library scans,

while swap was also in use. Together they pushed the drive past what it can serve, so reads queued for
tens of seconds and health checks (timeouts of 10-30 s) failed. The immediate trigger was never proven; the
contributing factors were.

## Follow-up findings

- A full-surface extended SMART self-test finished with **no errors**. Three pending sectors remained
  and are being monitored. One damaged media file that had been triggering a read error was removed.
- One container's default health check launched a full headless browser every 15 minutes, producing about
  5 GB of writes per day on a drive that was already struggling. I replaced it with a lightweight HTTP
  check every 2 minutes, which removed a steady source of wear and load.
- Restarting the photo service re-triggers the integrity scan, so a restart during an incident makes things
  worse. That is now documented in the service README.

## What went well

- Health checks and the watchdog detected the problem within minutes.
- The state-change alerting kept the signal readable instead of flooding the phone.
- Diagnosis used only built-in kernel interfaces, so it worked while the machine was struggling.

## What I changed

| Change | Purpose |
|---|---|
| [`disk-watch.sh`](../services/monitoring/disk-watch/disk-watch.sh) (cron, every 2 min) | Alert on kernel disk errors, read-only remount and sustained slow reads |
| `smartd` configuration with ntfy hook | Alert on SMART attribute changes; scheduled self-tests |
| Lightweight health check for the browser-based container | Remove avoidable writes |
| Documentation of the "do not restart the photo service" gotcha | Avoid making an incident worse |

## Lessons

1. **Health-check failures across unrelated services usually mean a shared resource problem**, such as
   disk, memory or network, not several bugs.
2. **Check pressure and latency, not just utilisation.** `iostat`-style "% busy" tells you it is saturated;
   latency and `/proc/pressure/io` tell you how badly.
3. **Monitoring hardware that cannot be replaced yet is still valuable.** The drive is still in use, but
   there is now an early-warning system around it.
4. **Defaults can be expensive.** A health check is code that runs forever; its cost should be reviewed.

## Still open

- Move the data to an SSD (the real fix).
- Off-site backup of irreplaceable data (photos).
- Stagger or schedule the heavy background jobs so they do not overlap.
