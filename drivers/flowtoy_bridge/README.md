# Feather FlowToy Bridge

This driver targets the same `feather_nrf52840_express` board family already
used by the Bluetooth bridge, but for a different job: receive-only capture of
FlowToy radio packets and forwarding them to Totem over USB serial.

## Problem statement

Totem needs a stable receive-side schema before we invest in command writes. The
Flowtoys reference bridge uses `RF24_250KBPS`, channel `2`, 3-byte addressing,
and 16-bit CRC. A bare nRF52840 proprietary radio is not a great fit for that
exact link budget and data rate, so the practical Feather path is:

- `Adafruit Feather nRF52840 Express` as the USB/host microcontroller
- external `nRF24L01+` radio frontend over SPI
- newline-delimited JSON packets over USB serial to Totem

## Materials

- `Adafruit Feather nRF52840 Express`
- `nRF24L01+` breakout or FeatherWing-compatible equivalent
- 3.3 V power rail and shared ground
- USB connection to the Pi/Totem host
- Arduino IDE or another Adafruit nRF52-capable build environment for the
  sketch in `arduino/`

## Repository layout

| File | Purpose |
| ---- | ------- |
| `code.py` | CircuitPython-friendly schema harness used for REPL checks and CI driver tests. |
| `settings.toml` | Feather nRF52840 Express metadata for the standard driver tooling. |
| `arduino/flowtoy_feather_nrf24_receiver/flowtoy_feather_nrf24_receiver.ino` | Manual receive-only firmware sketch for an external `nRF24L01+` radio. |

## Serial schema

Each received packet is emitted as one newline-delimited JSON object:

```json
{
  "event_type": "peripheral.radio.packet",
  "data": {
    "protocol": "flowtoy",
    "channel": 2,
    "bitrate_kbps": 250,
    "modulation": "nrf24-shockburst",
    "crc_ok": true,
    "payload": [1, 7, 241],
    "metadata": {
      "address": [1, 7, 241],
      "address_width_bytes": 3,
      "crc_bits": 16
    }
  }
}
```

Totem currently treats this as receive-only telemetry. The schema intentionally
leaves write commands out of scope for now. The bridge runtime is expected to
filter candidate payloads and only emit frames that match the known 21-byte
FlowToy sync-packet shape.

## Flashing paths

### Contract harness

Use the normal `totem update-driver --name flowtoy_bridge` flow if you only want
the CircuitPython harness on a Feather. This is useful for validating the USB
serial schema and identity responses, but it does not talk to the FlowToy RF
link by itself.

### Real receive firmware

Use the Arduino sketch when you want actual packet capture. That path is manual
today because the repo's `update-driver` tooling is CircuitPython-only.

## Totem integration

Point Totem at the bridge with:

```bash
HEART_RADIO_PORT=/dev/ttyACM0 totem run --configuration lib_2025
```

The host-side peripheral in `src/heart/peripheral/radio.py` will ingest the
JSON packets and publish `peripheral.radio.packet` events.
