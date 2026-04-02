# Flowtoys Connect Bridge Integration Note

## Problem statement

Heart needs a Flowtoys-compatible radio peripheral, but the first usable cut is
receive-only packet capture. The repository already had a receive-only
`RadioPeripheral` transport, but it did not expose FlowToy packets as a
first-class peripheral or reflect the real packet schema seen on hardware. This
note records the bridge contract and the hardware path that can realistically
run on the hardware we have: `feather_nrf52840_express`.

## Materials

- Host-side radio transport in [src/heart/peripheral/radio.py](../../src/heart/peripheral/radio.py)
- Host-side FlowToy peripheral in [src/heart/peripheral/flowtoy.py](../../src/heart/peripheral/flowtoy.py)
- FlowToy payload helper in [src/heart/peripheral/input_payloads/flowtoy.py](../../src/heart/peripheral/input_payloads/flowtoy.py)
- Payload normalization helper in [src/heart/peripheral/input_payloads/radio.py](../../src/heart/peripheral/input_payloads/radio.py)
- FlowToy packet matcher in [packages/heart-firmware-io/src/heart_firmware_io/flowtoy.py](../../packages/heart-firmware-io/src/heart_firmware_io/flowtoy.py)
- CircuitPython bridge harness in [drivers/flowtoy_bridge/code.py](../../drivers/flowtoy_bridge/code.py)
- Native Feather sketch in [drivers/flowtoy_bridge/arduino/flowtoy_feather_nrf52840_receiver/flowtoy_feather_nrf52840_receiver.ino](../../drivers/flowtoy_bridge/arduino/flowtoy_feather_nrf52840_receiver/flowtoy_feather_nrf52840_receiver.ino)
- Regression coverage in [tests/peripheral/test_radio_peripheral.py](../../tests/peripheral/test_radio_peripheral.py)
- Regression coverage in [tests/peripheral/test_flowtoy_peripheral.py](../../tests/peripheral/test_flowtoy_peripheral.py)
- Reference bridge firmware repository: [benkuper/FlowtoysConnectBridge](https://github.com/benkuper/FlowtoysConnectBridge)
- Native nRF52 RF24-compatible library: [TMRh20/nrf_to_nrf](https://github.com/TMRh20/nrf_to_nrf)

## Findings

The referenced bridge is centered on an `ESP32` host MCU paired with an
`nRF24L01` 2.4 GHz transceiver, not an `nRF52840`. The upstream repository uses
the `RF24` stack and exposes a serial command protocol that accepts
single-letter commands plus comma-separated arguments for sync, wake, power,
and pattern updates. It also configures the RF side for `RF24_250KBPS`,
channel `2`, 3-byte addressing, 16-bit CRC, and a fixed `SyncPacket` payload
size.

CircuitPython on `feather_nrf52840_express` does not currently expose the
proprietary radio controls needed to reproduce that RF24-style link. The
feasible split is:

1. Keep the CircuitPython driver in `drivers/flowtoy_bridge/` as the shared USB
   serial contract and CI-tested schema harness.
1. Use native Arduino firmware for real RF capture.

The chosen native path uses `nrf_to_nrf`, which provides an RF24-compatible API
for nRF52 devices and explicitly supports `NRF_250KBPS`. That does not prove
perfect wire compatibility with every upstream Flowtoys transmitter, but it is
the most credible internal-radio path for a bare Feather nRF52840. The repo's
`update-driver` command now supports an Arduino mode, and `flowtoy_bridge`
defaults to that mode so a standard driver update compiles and uploads the
native firmware instead of only copying the CircuitPython harness.

On the Heart side, the transport and peripheral split now models three
concerns:

1. Receive raw packets from a newline-delimited JSON serial stream and publish them as normalized `RadioPacket` transport events.
1. Decode the full 21-byte `SyncPacket` schema seen on hardware, including large group identifiers and zeroed default states.
1. Expose FlowToy packets as a first-class `FlowToyPeripheral` that publishes the full bridge JSON body plus a dynamic mode tag derived from the decoded `page`/`mode` pair.

## Command mapping

| Heart event/helper | Bridge command | Notes |
| --- | --- | --- |
| `sync_flow_toys(timeout_seconds=...)` | `s<timeout>` | Starts RF sync for a bounded or zero timeout window. |
| `stop_flow_toy_sync()` | `S` | Stops bridge sync mode. |
| `reset_flow_toy_sync()` | `a` | Resets sync state. |
| `wake_flow_toys(group_id, group_is_public)` | `w...` / `W...` | Uppercase targets public groups. |
| `power_off_flow_toys(group_id, group_is_public)` | `z...` / `Z...` | Uppercase targets public groups. |
| `set_flow_toy_pattern(pattern)` | `p...` / `P...` | Encodes the 13-field pattern payload expected by the bridge. |

## Implementation note

The current Heart integration deliberately stops at the serial bridge boundary.
It does not make the host process speak raw radio. If the firmware path changes
later, `RadioDriver` remains the seam to swap while keeping the transport and
FlowToy peripheral APIs stable.
