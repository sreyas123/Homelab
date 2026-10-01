# Home Assistant

Smart-home hub controlling a WiZ bulb and a Govee lantern **locally**, with no cloud account.

## Key points

- Runs with `network_mode: host` so device discovery and the light protocols (broadcast/multicast UDP) work.
- `config/configuration.yaml` adds shell commands, an input helper and two **template lights**:
  - **Desk Lantern**: brightness, colour, colour temperature and five software effects, driven by `govee_lantern.py` and `lantern_effects.py` over the device's UDP LAN API (the built-in integration only supports on/off for this model).
  - **Bedroom Lamp Fixed**: wraps the WiZ bulb and always sets the white LED to 0 when a colour is chosen, fixing washed-out colours caused by the stock RGBW colour picker.
- Empty `automations.yaml`, `scripts.yaml`, `scenes.yaml` and a `themes/` folder are included because `configuration.yaml` includes them.
- Put your own lantern IP address in the two `.py` files (bracketed notes mark the spot).
- The real `config` folder also holds accounts, a database and secrets; those are **not** in this repo.
- Docker creates the real `config` folder as root, so edit it with `sudo` or from inside the container.

## Files

- `config`
- `docker-compose.yml`

Secrets and personal values are not stored here; see `.env.example` where present.
