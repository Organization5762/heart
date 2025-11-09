# Radio Peripheral Skeleton

## Overview

`heart.peripheral.radio.RadioPeripheral` normalises data coming from a USB
bridge that emits proprietary 2.4 GHz packets. The runtime subscribes to the new
`peripheral.radio.packet` event type, which wraps raw payload bytes together with
frequency, channel, modulation, and RSSI metadata. The module currently assumes
an empty payload so the rest of the event pipeline can be wired up before the
actual FlowToys transceiver is documented.

## Host integration

- `SerialRadioDriver` listens on a newline-delimited JSON stream. Configure the
  bridge port via the `HEART_RADIO_PORT` environment variable (comma-separated
  when multiple receivers are attached).
- Each JSON object must include a top-level `data` mapping. Known keys include:
  `frequency_hz`, `channel`, `modulation`, `rssi_dbm`, `payload`, and `metadata`.
  Missing values default to `None` or an empty payload.
- `RadioPeripheral.process_packet` stores the latest raw packet for inspection
  and publishes a `RadioPacket` onto the event bus. Tests assert the payload is
  converted to a list of unsigned bytes so downstream consumers see stable types.

## Firmware stub

The new `drivers/radio_bridge` bundle contains a CircuitPython runtime that emits
placeholder packets:

```json
{"event_type": "peripheral.radio.packet", "data": {}}
```

The firmware keeps the identify handshake wired up via `heart.firmware_io.identity`
so tools such as `scripts/driver_loader.py` can recognise the bridge. Replace the
`_default_packet` helper with radio-specific reads once the FlowToys protocol is
reverse engineered.

## Next steps

1. Capture actual bridge traffic and extend `SerialRadioDriver._decode` with the
   necessary parsing logic (payload framing, checksum handling, etc.).
1. Track per-prop addressing so multiple FlowToys can be controlled concurrently.
1. Consider exposing RSSI trends on the event bus for debugging range issues.
