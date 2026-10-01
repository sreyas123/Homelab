#!/usr/bin/env python3
"""Software light effects for the Govee lantern (LAN API has no scene support).
Runs until killed. Exits by itself if the server-alert bridge raises /shared/alert."""
import colorsys, json, math, os, random, socket, sys, time

IP = "192.168.0.110"  # (Put your own lantern's IP address here instead of this example)
ALERT_FLAG = "/shared/alert"
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(cmd, data):
    s.sendto(json.dumps({"msg": {"cmd": cmd, "data": data}}).encode(), (IP, 4003))


def rgb(r, g, b):
    send("colorwc", {"color": {"r": int(r), "g": int(g), "b": int(b)}, "colorTemInKelvin": 0})


def bright(v):
    send("brightness", {"value": max(1, min(100, int(v)))})


def hue(h, sat=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, sat, 1.0)
    rgb(r * 255, g * 255, b * 255)


def tick(delay):
    if os.path.exists(ALERT_FLAG):
        sys.exit(0)
    time.sleep(delay)


def rainbow():
    h = 0.0
    bright(80)
    while True:
        hue(h); h += 0.01; tick(0.4)


def breathe():
    rgb(80, 180, 255)
    t = 0.0
    while True:
        bright(10 + 90 * (0.5 - 0.5 * math.cos(t))); t += 0.25; tick(0.3)


def candle():
    rgb(255, 110, 20)
    while True:
        bright(random.randint(25, 85)); tick(random.uniform(0.1, 0.4))


def aurora():
    bright(70)
    t = 0.0
    while True:
        hue(0.33 + 0.28 * (0.5 - 0.5 * math.cos(t))); t += 0.05; tick(0.4)


def party():
    bright(100)
    while True:
        hue(random.random()); tick(0.7)


EFFECTS = {"rainbow": rainbow, "breathe": breathe, "candle": candle,
           "aurora": aurora, "party": party}

if __name__ == "__main__":
    if os.path.exists(ALERT_FLAG):
        sys.exit(0)
    send("turn", {"value": 1})
    EFFECTS[sys.argv[1]]()
