# Design decisions

Short records of why things are built the way they are.

## Docker Compose for everything
**Why:** each service is isolated, upgrades are one command, and the whole server is described by text files
that live in version control. Compose is enough for a single host; Kubernetes would add complexity with no
benefit.

## Secrets in `.env`, not in the Compose files
**Why:** the files can be committed and shared; values stay on the machine. Each folder includes an
`.env.example` documenting what is required.

## Local-first smart home (no cloud)
**Why:** it keeps working during an internet outage, is faster, and needs no vendor account or API key. Both
lights are driven over their local network protocols.

## Custom scripts for the lantern instead of the built-in integration
**Why:** Home Assistant's built-in support for this lantern model only provided on/off. The device
documents a UDP LAN API (JSON commands), so two small scripts add brightness, colour and effects.
Vendor scenes cannot be triggered over that API, so I implemented a handful of effects in software
(rainbow, breathe, candle, aurora, party).

## A wrapper ("template") light for the WiZ bulb
**Why:** the bulb has separate colour LEDs and a white LED. Home Assistant's colour picker kept the previous
white level, which washed colours out (pure blue looked yellowish-white). A template light always sets the
white channel to 0 when a colour is chosen and passes everything else through to the real entity. The original
entity is hidden, not deleted, because the wrapper depends on it.

## Alerting on state changes
**Why:** alerting every minute on the same problem trains you to ignore alerts. The watchdog stores state and
sends one message when something breaks and one when it recovers.

## A physical status light that only reflects recoverable problems
**Why:** a status light is only useful if it can return to normal. Container and resource alerts recover;
hardware errors do not. Hardware warnings go to the phone only.

## Keeping the hard drive and monitoring it
**Why:** replacing the drive was not an option right now. The drive passes its health checks; the problem is
performance under load. Early-warning alerts (kernel errors, latency, SMART) buy time. The real fix, an SSD,
is on the roadmap.

## Staying on the desktop OS instead of going headless
**Why:** I measured the desktop's memory use: roughly 200-250 MB of 8 GB. That is too small a gain to justify
the risk. (One caveat if this changes: without the desktop's power settings, closing the laptop lid would
suspend the machine unless `HandleLidSwitch=ignore` is set.)

## Disabling unused desktop extras
**Why:** nothing on the server uses the Bluetooth applet, update tray or mail/calendar background services.
They are disabled through autostart overrides, which are trivial to undo.

## A small custom dashboard instead of Prometheus and Grafana
**Why:** the question I need answered is "is anything wrong right now, and how busy is it?". A Prometheus and
Grafana stack would use more memory and disk than this laptop can spare and adds several moving parts. A single
Python file reading `/proc` and cgroups answers the question using about 25 MB of RAM. The cost is no long-term
history; a time-series stack is listed as a future improvement if trends ever matter.

## A glass-style interface that adapts to the screen
**Why:** the dashboards are mostly used on a phone, in either orientation. They use fluid grids and a few
breakpoints (including a short-and-wide landscape layout) instead of separate pages, and a lighter blur on small
screens so scrolling stays smooth on mid-range hardware.
