#!/usr/bin/env python3
"""Send Govee LAN API commands to the desk lantern (H1630). Usage:
govee_lantern.py off | on | bright N | rgb R G B | temp K | effect NAME
Any command except `effect` stops a running software effect first."""
import json, os, signal, socket, subprocess, sys

IP = "192.168.0.110"  # (Put your own lantern's IP address here instead of this example)
PIDFILE = "/config/.lantern_effect.pid"
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(cmd, data):
    s.sendto(json.dumps({"msg": {"cmd": cmd, "data": data}}).encode(), (IP, 4003))


def stop_effect():
    try:
        with open(PIDFILE) as f:
            os.kill(int(f.read()), signal.SIGTERM)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        pass
    try:
        os.remove(PIDFILE)
    except FileNotFoundError:
        pass


a = sys.argv[1:]
stop_effect()
if a[0] == "off":
    send("turn", {"value": 0})
elif a[0] == "on":
    send("turn", {"value": 1})
elif a[0] == "bright":
    send("turn", {"value": 1}); send("brightness", {"value": max(1, min(100, int(a[1])))})
elif a[0] == "rgb":
    send("turn", {"value": 1})
    send("colorwc", {"color": {"r": int(a[1]), "g": int(a[2]), "b": int(a[3])}, "colorTemInKelvin": 0})
elif a[0] == "temp":
    send("turn", {"value": 1})
    send("colorwc", {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": int(a[1])})
elif a[0] == "effect":
    p = subprocess.Popen([sys.executable, "/config/lantern_effects.py", a[1]],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    with open(PIDFILE, "w") as f:
        f.write(str(p.pid))
