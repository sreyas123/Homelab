#!/usr/bin/env python3
"""status-dashboard: live server status API plus a single-page web UI.

Standard library only. Everything is read from the host: /proc (CPU, memory, load, pressure),
the root filesystem, thermal zones, the Docker API (container list and health) and the cgroup
files that back `docker stats` (per-container CPU and memory) - the cgroup files are far cheaper
to read than the stats API, which matters on a slow machine.

Endpoints (GET only, no secrets, nothing is written to disk):
  /                      the dashboard page
  /api/status            everything, as JSON
  /api/summary           a few flat numbers (for dashboard widgets)
  /api/service/<name>    one container, flat (for dashboard widgets)
  /api/history           recent samples for the sparklines
  /healthz               liveness check
"""
import http.client
import http.server
import json
import os
import random
import re
import socket
import threading
import time
from socketserver import ThreadingMixIn

PORT = int(os.environ.get("PORT", "3002"))
HOSTFS = os.environ.get("HOSTFS", "/hostfs")          # host root, read-only: used for disk usage
HOSTSYS = os.environ.get("HOSTSYS", "/hostsys")       # host /sys, read-only: temperatures and cgroups
SERVER_NAME = os.environ.get("SERVER_NAME", "Home Server")
SERVICES_FILE = os.environ.get("SERVICES_FILE", "/app/services.json")
DEMO = os.environ.get("DEMO") == "1"                  # synthetic data, for screenshots and development
DISK_WARN = int(os.environ.get("DISK_WARN_PCT", "85"))
MEM_WARN = int(os.environ.get("MEM_WARN_PCT", "90"))
IO_WARN = float(os.environ.get("IO_WARN_PCT", "30"))
HERE = os.path.dirname(os.path.abspath(__file__))
HIST_LEN = 180                                        # samples kept for sparklines (15 min at 5 s)

lock = threading.Lock()
state = {"host": {}, "containers": [], "problems": [], "overall": "ok", "ts": 0}
history = {"cpu": [], "mem": [], "io": [], "disk": []}


# ---------------------------------------------------------------- helpers
def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def load_services():
    try:
        with open(SERVICES_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class DockerConn(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=8)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(8)
        self.sock.connect("/var/run/docker.sock")


def docker_get(path):
    conn = DockerConn()
    try:
        conn.request("GET", path)
        return json.loads(conn.getresponse().read())
    finally:
        conn.close()


# ---------------------------------------------------------------- host metrics
_prev_cpu = [None]


def cpu_percent():
    parts = read("/proc/stat").split("\n", 1)[0].split()[1:]
    vals = [int(x) for x in parts[:8]]
    idle = vals[3] + vals[4]
    total = sum(vals)
    prev = _prev_cpu[0]
    _prev_cpu[0] = (idle, total)
    if not prev or total == prev[1]:
        return 0.0
    return round(100.0 * (1 - (idle - prev[0]) / (total - prev[1])), 1)


def meminfo():
    info = {}
    for line in read("/proc/meminfo").splitlines():
        k, _, v = line.partition(":")
        info[k] = int(v.split()[0]) * 1024 if v.strip() else 0
    total, avail = info.get("MemTotal", 1), info.get("MemAvailable", 0)
    swap_t, swap_f = info.get("SwapTotal", 0), info.get("SwapFree", 0)
    return {
        "mem_total": total, "mem_used": total - avail, "mem_pct": round(100 * (total - avail) / total, 1),
        "swap_total": swap_t, "swap_used": swap_t - swap_f,
        "swap_pct": round(100 * (swap_t - swap_f) / swap_t, 1) if swap_t else 0.0,
    }


def pressure(kind="io"):
    out = {}
    for line in read(f"/proc/pressure/{kind}").splitlines():
        parts = line.split()
        if not parts:
            continue
        out[parts[0]] = {k: float(v) for k, v in (p.split("=") for p in parts[1:] if p.startswith("avg"))}
    return out


def temperature():
    best, any_t = None, []
    base = f"{HOSTSYS}/class/thermal"
    try:
        zones = [z for z in os.listdir(base) if z.startswith("thermal_zone")]
    except OSError:
        return None
    for z in zones:
        try:
            t = int(read(f"{base}/{z}/temp", "0")) / 1000.0
        except ValueError:
            continue
        any_t.append(t)
        if read(f"{base}/{z}/type").strip() == "x86_pkg_temp":
            best = t
    return round(best if best is not None else max(any_t, default=0), 1) or None


def disk_usage():
    try:
        st = os.statvfs(HOSTFS)
    except OSError:
        return {"disk_total": 0, "disk_used": 0, "disk_pct": 0.0}
    total = st.f_blocks * st.f_frsize
    avail = st.f_bavail * st.f_frsize
    return {"disk_total": total, "disk_used": total - avail, "disk_pct": round(100 * (1 - st.f_bavail / st.f_blocks), 1)}


def host_metrics():
    pio, pmem = pressure("io"), pressure("memory")
    load = read("/proc/loadavg").split()
    m = {
        "cpu_pct": cpu_percent(), "cores": os.cpu_count() or 1,
        "load": [float(x) for x in load[:3]] if load else [0, 0, 0],
        "uptime_s": int(float(read("/proc/uptime", "0 0").split()[0])),
        "io_some10": pio.get("some", {}).get("avg10", 0.0), "io_full10": pio.get("full", {}).get("avg10", 0.0),
        "io_full60": pio.get("full", {}).get("avg60", 0.0), "io_some60": pio.get("some", {}).get("avg60", 0.0),
        "mem_some10": pmem.get("some", {}).get("avg10", 0.0),
        "temp_c": temperature(),
    }
    m.update(meminfo())
    m.update(disk_usage())
    return m


# ---------------------------------------------------------------- containers
_prev_c = {}


def cgroup_dir(cid):
    for tmpl in ("system.slice/docker-{}.scope", "docker/{}"):
        p = f"{HOSTSYS}/fs/cgroup/" + tmpl.format(cid)
        if os.path.isdir(p):
            return p
    return None


def container_usage(cid, now):
    d = cgroup_dir(cid)
    if not d:
        return None, None
    mem = None
    try:
        cur = int(read(f"{d}/memory.current", "0"))
        inactive = 0
        for line in read(f"{d}/memory.stat").splitlines():
            if line.startswith("inactive_file "):
                inactive = int(line.split()[1])
                break
        mem = max(cur - inactive, 0)
    except ValueError:
        pass
    cpu = None
    for line in read(f"{d}/cpu.stat").splitlines():
        if line.startswith("usage_usec"):
            usec = int(line.split()[1])
            prev = _prev_c.get(cid)
            _prev_c[cid] = (usec, now)
            if prev and now > prev[1]:
                cpu = round(100.0 * (usec - prev[0]) / 1e6 / (now - prev[1]), 1)   # % of one core
            break
    return cpu, mem


def collect_containers(cfg):
    now = time.time()
    hidden = set(cfg.get("hidden", []))
    meta = cfg.get("containers", {})
    out = []
    for c in docker_get("/containers/json?all=true"):
        name = c["Names"][0].lstrip("/")
        if name in hidden:
            continue
        status = c.get("Status", "")
        health = "none"
        m = re.search(r"\((healthy|unhealthy|health: starting)\)", status)
        if m:
            health = {"healthy": "healthy", "unhealthy": "unhealthy"}.get(m.group(1), "starting")
        cpu, mem = (None, None)
        if c["State"] == "running":
            cpu, mem = container_usage(c["Id"], now)
        info = meta.get(name, {})
        ports = sorted({p["PublicPort"] for p in c.get("Ports", []) if p.get("PublicPort")})
        out.append({
            "name": name, "label": info.get("label", name), "desc": info.get("desc", ""),
            "group": info.get("group", "Other"), "state": c["State"], "health": health, "status": status,
            "cpu": cpu, "mem": mem, "port": info.get("port", ports[0] if ports else None),
            "scheme": info.get("scheme", "http"), "link": info.get("link", True),
        })
    out.sort(key=lambda x: (x["group"], x["label"].lower()))
    return out


def derive_problems(host, containers):
    problems = []
    for c in containers:
        if c["state"] != "running":
            problems.append({"level": "bad", "kind": "container", "name": c["label"], "text": f"{c['label']} is {c['state']}"})
        elif c["health"] == "unhealthy":
            problems.append({"level": "bad", "kind": "container", "name": c["label"], "text": f"{c['label']} is unhealthy"})
    if host["disk_pct"] >= DISK_WARN:
        problems.append({"level": "warn", "kind": "disk", "name": "Disk", "text": f"Disk is {host['disk_pct']:.0f}% full"})
    if host["mem_pct"] >= MEM_WARN:
        problems.append({"level": "warn", "kind": "memory", "name": "Memory", "text": f"Memory is {host['mem_pct']:.0f}% used"})
    if host["io_full60"] >= IO_WARN:
        problems.append({"level": "warn", "kind": "io", "name": "Disk I/O", "text": f"Disk is struggling ({host['io_full60']:.0f}% of time stalled)"})
    overall = "bad" if any(p["level"] == "bad" for p in problems) else "warn" if problems else "ok"
    return problems, overall


# ---------------------------------------------------------------- demo data (screenshots, development)
_demo = {"cpu": 14.0, "mem": 48.0, "io": 4.0, "disk": 22.0}
DEMO_SERVICES = [
    ("jellyfin", "Media Server", "Media", "Your own movies, shows and music library", 8096),
    ("navidrome", "Music Streaming", "Media", "Stream the music collection anywhere", 4533),
    ("immich_server", "Photos", "Media", "Photo and video backup with search", 2283),
    ("immich_postgres", "Photo Database", "Background", "PostgreSQL for the photo service", None),
    ("immich_redis", "Photo Cache", "Background", "In-memory cache", None),
    ("immich_machine_learning", "Photo AI", "Background", "Face and object recognition", None),
    ("homeassistant", "Smart Home", "Home", "Lights and automations, local control", 8123),
    ("light-alerts", "Lantern Alerts", "Home", "Turns a lamp red or green with server status", None),
    ("homepage", "Dashboard", "Monitoring", "Phone-friendly start page", 3001),
    ("server-watcher", "Watchdog", "Monitoring", "Checks every service once a minute", None),
    ("status-dashboard", "Live Status", "Monitoring", "This page", 3002),
    ("portainer", "Container Admin", "Admin", "Inspect and manage containers", 9443),
]


def demo_collect():
    for k, (lo, hi, step) in {"cpu": (4, 55, 5), "mem": (40, 62, 1.2), "io": (0, 22, 3), "disk": (22, 22.4, 0.02)}.items():
        _demo[k] = min(hi, max(lo, _demo[k] + random.uniform(-step, step)))
    total = 8 * 1024 ** 3
    host = {
        "cpu_pct": round(_demo["cpu"], 1), "cores": 8, "load": [0.8, 0.7, 0.6], "uptime_s": 53 * 86400 + 4 * 3600,
        "io_some10": _demo["io"], "io_full10": _demo["io"] * 0.8, "io_full60": _demo["io"] * 0.7, "io_some60": _demo["io"],
        "mem_some10": 0.5, "temp_c": 41.0 + _demo["cpu"] / 10,
        "mem_total": total, "mem_used": int(total * _demo["mem"] / 100), "mem_pct": round(_demo["mem"], 1),
        "swap_total": 8 * 1024 ** 3, "swap_used": int(1.1 * 1024 ** 3), "swap_pct": 13.8,
        "disk_total": 916 * 1000 ** 3, "disk_used": int(916 * 1000 ** 3 * _demo["disk"] / 100), "disk_pct": round(_demo["disk"], 1),
    }
    cons = []
    for name, label, group, desc, port in DEMO_SERVICES:
        cons.append({"name": name, "label": label, "desc": desc, "group": group, "state": "running", "health": "healthy",
                     "status": "Up 6 weeks (healthy)", "cpu": round(random.uniform(0, 4), 1),
                     "mem": int(random.uniform(30, 420) * 1024 ** 2), "port": port, "scheme": "https" if port == 9443 else "http", "link": True})
    if os.environ.get("DEMO_BAD"):
        cons[1].update(state="running", health="unhealthy", status="Up 2 hours (unhealthy)")
        host.update(io_full60=44.0, io_some10=61.0)
    cons.sort(key=lambda x: (x["group"], x["label"].lower()))
    return host, cons


# ---------------------------------------------------------------- collector thread
def push_history(host):
    with lock:
        for k, v in (("cpu", host["cpu_pct"]), ("mem", host["mem_pct"]), ("io", host["io_some10"]), ("disk", host["disk_pct"])):
            history[k].append(round(v, 1))
            del history[k][:-HIST_LEN]


def collector():
    cfg = load_services()
    last_c = 0.0
    containers = []
    while True:
        t0 = time.time()
        try:
            if DEMO:
                host, containers = demo_collect()
            else:
                host = host_metrics()
                if t0 - last_c >= 10:
                    containers = collect_containers(cfg)
                    last_c = t0
            problems, overall = derive_problems(host, containers)
            push_history(host)
            with lock:
                state.update(host=host, containers=containers, problems=problems, overall=overall, ts=time.time())
        except Exception as e:  # keep serving the last good data
            print(f"collector error: {type(e).__name__}: {e}", flush=True)
        time.sleep(max(0.5, 5 - (time.time() - t0)))


# ---------------------------------------------------------------- HTTP
def snapshot():
    with lock:
        return json.loads(json.dumps(state))


def summary():
    s = snapshot()
    h, cons = s["host"], s["containers"]
    ok = sum(1 for c in cons if c["state"] == "running" and c["health"] != "unhealthy")
    return {
        "status": {"ok": "All good", "warn": "Attention", "bad": "Problem"}[s["overall"]],
        "containers": f"{ok} / {len(cons)}", "problems": len(s["problems"]),
        "cpu": round(h.get("cpu_pct", 0)), "memory": round(h.get("mem_pct", 0)), "disk": round(h.get("disk_pct", 0)),
        "io": round(h.get("io_some10", 0)), "temp": round(h.get("temp_c") or 0), "load": h.get("load", [0])[0],
    }


def service_flat(name):
    for c in snapshot()["containers"]:
        if c["name"] == name:
            health = c["health"] if c["health"] != "none" else "ok"
            return {"state": c["state"].capitalize(), "health": health.capitalize(), "cpu": round(c["cpu"] or 0, 1),
                    "mem": round((c["mem"] or 0) / 1024 ** 2), "status": c["status"]}
    return None


def page():
    html = read(os.path.join(HERE, "static", "index.html"))
    init = json.dumps({"state": snapshot(), "history": history, "server": SERVER_NAME, "demo": DEMO}).replace("</", "<\\/")
    return html.replace("/*__INIT__*/null", init).replace("__SERVER_NAME__", SERVER_NAME).encode()


STATIC = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"), "/icon.svg": ("icon.svg", "image/svg+xml")}
SEC = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "SAMEORIGIN",
       "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):          # no per-request logging: avoids pointless writes on a slow disk
        pass

    def send(self, code, body, ctype, cache="no-store"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        for k, v in SEC.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, obj, code=200):
        self.send(code, json.dumps(obj).encode(), "application/json")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self.send(200, page(), "text/html; charset=utf-8")
        if path == "/api/status":
            return self.json({"server": SERVER_NAME, **snapshot()})
        if path == "/api/summary":
            return self.json(summary())
        if path == "/api/history":
            with lock:
                return self.json(history)
        if path.startswith("/api/service/"):
            data = service_flat(path.rsplit("/", 1)[1])
            return self.json(data, 200) if data else self.json({"error": "unknown service"}, 404)
        if path == "/healthz":
            return self.send(200, b"ok", "text/plain")
        if path in STATIC:
            fn, ct = STATIC[path]
            body = read(os.path.join(HERE, "static", fn)).replace("__SERVER_NAME__", SERVER_NAME)
            return self.send(200, body.encode(), ct, "public, max-age=3600")
        self.send(404, b"not found", "text/plain")


class Server(ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    threading.Thread(target=collector, daemon=True).start()
    time.sleep(1.5)       # let the first sample land so the first page load has data
    print(f"status-dashboard listening on :{PORT} (demo={DEMO})", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
