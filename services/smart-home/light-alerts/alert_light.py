#!/usr/bin/env python3
"""Bridge: server-watcher ntfy alerts -> Govee lantern (LAN API, UDP 4003).
Any outstanding problem = solid red (flashes on each new alert). When everything
has recovered: green for a while, then back to warm white."""
import json, os, socket, time, urllib.request

TOPIC = os.environ["NTFY_TOPIC"]
LANTERN = os.environ.get("LANTERN_IP", "192.168.0.110")  # (Put your own lantern's IP address here, or set LANTERN_IP in the compose file - 192.168.0.110 is only an example)
GREEN_SECONDS = int(os.environ.get("GREEN_SECONDS", "20"))
REST_KELVIN = int(os.environ.get("REST_KELVIN", "2700"))
REST_BRIGHTNESS = int(os.environ.get("REST_BRIGHTNESS", "40"))

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
active = set()
FLAG = "/shared/alert"  # tells the lantern's software effects to stand down


def sync_flag():
    try:
        if active:
            open(FLAG, "w").close()
        elif os.path.exists(FLAG):
            os.remove(FLAG)
    except OSError as e:
        print(f"flag error: {e}", flush=True)


def send(cmd, data):
    msg = json.dumps({"msg": {"cmd": cmd, "data": data}}).encode()
    sock.sendto(msg, (LANTERN, 4003))


def colour(r, g, b, bright=100):
    send("turn", {"value": 1})
    send("brightness", {"value": bright})
    send("colorwc", {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0})


def flash_red():
    for _ in range(3):
        colour(255, 0, 0, 100); time.sleep(0.4)
        send("brightness", {"value": 5}); time.sleep(0.4)
    colour(255, 0, 0, 100)


def rest():
    send("turn", {"value": 1})
    send("brightness", {"value": REST_BRIGHTNESS})
    send("colorwc", {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": REST_KELVIN})


def classify(title):
    t = title.strip()
    low = t.lower()
    if t.startswith("DOWN:"):
        return "add", t[5:].strip()
    if t.startswith("DISK ALERT"):
        return "add", "disk"
    if t.startswith("MEMORY ALERT"):
        return "add", "memory"
    if t.startswith("RECOVERED:"):
        rest_ = t[10:].strip()
        if low.startswith("recovered: disk"):
            return "del", "disk"
        if low.startswith("recovered: memory"):
            return "del", "memory"
        return "del", rest_
    return None, None


def handle(title):
    action, key = classify(title)
    if action == "add":
        new = key not in active
        active.add(key)
        sync_flag()
        print(f"ALERT {key} (active={sorted(active)})", flush=True)
        if new:
            time.sleep(1)  # let any running effect notice the flag and exit
            flash_red()
    elif action == "del" and key in active:
        active.discard(key)
        sync_flag()
        print(f"RECOVERED {key} (active={sorted(active)})", flush=True)
        if not active:
            colour(0, 255, 0, 100)
            time.sleep(GREEN_SECONDS)
            if not active:
                rest()


def main():
    print(f"listening on ntfy topic, lantern={LANTERN}", flush=True)
    while True:
        try:
            with urllib.request.urlopen(f"https://ntfy.sh/{TOPIC}/json", timeout=90) as r:
                for line in r:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("event") == "message":
                        handle(ev.get("title", ""))
        except Exception as e:
            print(f"stream error: {e}; retrying", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
