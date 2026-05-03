# Feather FlowToy Bridge

This driver targets the same `feather_nrf52840_express` board family already
used by the Bluetooth bridge, but for a different job: receive-only capture of
FlowToy radio packets and forwarding them to Totem over USB serial.

## Problem statement

Totem needs a stable receive-side schema before we invest in command writes. The
Flowtoys reference bridge uses `RF24_250KBPS`, channel `2`, 3-byte addressing,
and 16-bit CRC. CircuitPython on `feather_nrf52840_express` does not expose the
needed proprietary radio controls, so the driver is split into two pieces:

- a CircuitPython harness for the USB serial contract and CI coverage
- a native Arduino sketch for actual packet capture on the Feather's internal
  2.4 GHz radio via `nrf_to_nrf`
- newline-delimited JSON packets over USB serial to Totem

## Materials

- `Adafruit Feather nRF52840 Express`
- USB connection to the Pi/Totem host
- Arduino IDE or another Adafruit nRF52-capable build environment for the
  sketch in `arduino/`
- `nrf_to_nrf` Arduino library by TMRh20

## Repository layout

| File | Purpose |
| ---- | ------- |
| `code.py` | CircuitPython-friendly schema harness used for REPL checks and CI driver tests. |
| `settings.toml` | Feather nRF52840 Express metadata for the standard driver tooling. |
| `arduino/flowtoy_feather_nrf52840_receiver/flowtoy_feather_nrf52840_receiver.ino` | Native receive-only firmware sketch that uses the Feather's internal 2.4 GHz radio. |
| `arduino/README.md` | Native firmware flashing notes and dependency list. |

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
emit the known 21-byte FlowToy sync-packet payloads and let the host decode
their full schema.

## Flashing paths

### Contract harness

Use `totem update-driver --name flowtoy_bridge --mode circuitpython` if you only
want the CircuitPython harness on a Feather. This is useful for validating the
USB serial schema and identity responses, but it does not talk to the FlowToy
RF link by itself.

### Real receive firmware

Use `totem update-driver --name flowtoy_bridge` for the default native firmware
path. The updater now compiles and flashes the Arduino sketch under
`arduino/flowtoy_feather_nrf52840_receiver/` with `arduino-cli`.

## Totem integration

Point Totem at the bridge with:

```bash
HEART_RADIO_PORT=/dev/ttyACM0 totem run --configuration lib_2025
```

The host-side transport in `src/heart/peripheral/radio.py` ingests the JSON
packets, and the FlowToy peripheral in `src/heart/peripheral/flowtoy.py`
publishes `peripheral.flowtoy.packet` events with the full JSON body plus a
mode label derived from the decoded `page`/`mode` pair.
