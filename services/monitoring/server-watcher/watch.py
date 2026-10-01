#!/usr/bin/env python3
"""Generic server watcher: polls Docker state + host disk/memory, alerts via ntfy
on any bad transition. Auto-discovers containers — no per-app config needed."""
import json
import os
import time
import urllib.request
import urllib.error
import socket
import http.client

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))
DISK_WARN_PCT = int(os.environ.get("DISK_WARN_PCT", "85"))
DISK_CRIT_PCT = int(os.environ.get("DISK_CRIT_PCT", "95"))
MEM_WARN_PCT = int(os.environ.get("MEM_WARN_PCT", "90"))
STATE_PATH = "/state/state.json"
HOSTFS = "/hostfs"


class DockerSocketConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost")

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect("/var/run/docker.sock")


def docker_get(path):
    conn = DockerSocketConnection()
    conn.request("GET", path)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return json.loads(data)


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"containers": {}, "disk": "ok", "mem": "ok"}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)


def notify(title, message, priority="default", tags=None):
    # ntfy headers must be Latin-1 (http.client encodes header values that way);
    # keep any emoji/unicode in the body only, never in the Title header.
    ascii_title = title.encode("ascii", "ignore").decode("ascii").strip() or "Server alert"
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": ascii_title,
            "Priority": priority,
            **({"Tags": ",".join(tags)} if tags else {}),
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except (urllib.error.URLError, UnicodeEncodeError) as e:
        print(f"ntfy send failed: {e}")


def container_health(c):
    inspect = docker_get(f"/containers/{c['Id']}/json")
    state = inspect.get("State", {})
    status = state.get("Status", "unknown")
    health = state.get("Health", {}).get("Status")
    return status, health


def is_bad_state(status, health):
    return status != "running" or health == "unhealthy"


def check_containers(state):
    containers = docker_get("/containers/json?all=true")
    seen = set()
    for c in containers:
        name = c["Names"][0].lstrip("/")
        seen.add(name)
        status, health = container_health(c)
        combined = f"{status}:{health}" if health else status
        bad = is_bad_state(status, health)
        prev = state["containers"].get(name)

        if prev is None:
            state["containers"][name] = {"combined": combined, "bad": bad}
            if bad:
                notify(
                    f"New container: {name}",
                    f"First seen in state {combined} — now tracking.",
                    priority="high",
                    tags=["warning"],
                )
            else:
                notify(
                    "New container detected",
                    f"{name} is now being tracked (state: {combined}).",
                )
            continue

        prev_combined = prev["combined"]
        prev_bad = prev["bad"]
        if combined != prev_combined:
            if bad and not prev_bad:
                notify(
                    f"DOWN: {name}",
                    f"{name} changed from '{prev_combined}' to '{combined}'.",
                    priority="urgent",
                    tags=["rotating_light"],
                )
            elif prev_bad and not bad:
                notify(
                    f"RECOVERED: {name}",
                    f"{name} is back to '{combined}'.",
                )
            state["containers"][name] = {"combined": combined, "bad": bad}

    gone = set(state["containers"]) - seen
    for name in gone:
        notify(
            f"Container removed: {name}",
            f"{name} no longer exists on the server (was '{state['containers'][name]['combined']}').",
        )
        del state["containers"][name]


def check_disk(state):
    st = os.statvfs(HOSTFS)
    used_pct = round((1 - st.f_bavail / st.f_blocks) * 100)
    level = "crit" if used_pct >= DISK_CRIT_PCT else "warn" if used_pct >= DISK_WARN_PCT else "ok"
    if level != state.get("disk", "ok"):
        if level in ("warn", "crit"):
            notify(
                f"DISK ALERT: {used_pct}% used",
                f"Root filesystem is {used_pct}% full (threshold {DISK_WARN_PCT if level=='warn' else DISK_CRIT_PCT}%).",
                priority="urgent" if level == "crit" else "high",
                tags=["floppy_disk"],
            )
        else:
            notify("RECOVERED: disk usage normal", f"Root filesystem now {used_pct}% full.")
    state["disk"] = level


def check_mem(state):
    with open(f"{HOSTFS}/proc/meminfo") as f:
        info = {}
        for line in f:
            k, v = line.split(":", 1)
            info[k] = int(v.strip().split()[0])
    total = info["MemTotal"]
    avail = info["MemAvailable"]
    used_pct = round((1 - avail / total) * 100)
    level = "warn" if used_pct >= MEM_WARN_PCT else "ok"
    if level != state.get("mem", "ok"):
        if level == "warn":
            notify(
                f"MEMORY ALERT: {used_pct}% used",
                f"System memory is {used_pct}% used.",
                priority="high",
                tags=["warning"],
            )
        else:
            notify("RECOVERED: memory usage normal", f"System memory now {used_pct}% used.")
    state["mem"] = level


def main():
    state = load_state()
    print(f"watcher started, tracking {len(state['containers'])} known container(s)")
    while True:
        try:
            check_containers(state)
            check_disk(state)
            check_mem(state)
            save_state(state)
        except Exception as e:
            print(f"watcher error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
