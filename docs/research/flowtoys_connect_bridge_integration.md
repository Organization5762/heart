# Flowtoys Connect Bridge Integration Note

## Problem statement

Heart needs a bidirectional radio peripheral for Flowtoys props. The repository already had a receive-only `RadioPeripheral` skeleton, but it did not publish packets onto its observable stream or encode outbound bridge commands. This note records the bridge contract and the hardware assumption used for the first read-write integration.

## Materials

- Host-side peripheral implementation in [src/heart/peripheral/radio.py](../../src/heart/peripheral/radio.py)
- Payload normalization helper in [src/heart/peripheral/input_payloads/radio.py](../../src/heart/peripheral/input_payloads/radio.py)
- Regression coverage in [tests/peripheral/test_radio_peripheral.py](../../tests/peripheral/test_radio_peripheral.py)
- Reference bridge firmware repository: [benkuper/FlowtoysConnectBridge](https://github.com/benkuper/FlowtoysConnectBridge)

## Findings

The referenced bridge is centered on an `ESP32` host MCU paired with an `nRF24L01` 2.4 GHz transceiver, not an `nRF52840`. The upstream repository uses the `RF24` stack and exposes a serial command protocol that accepts single-letter commands plus comma-separated arguments for sync, wake, power, and pattern updates. That makes the correct first integration target a serial bridge compatible with the upstream command grammar rather than a direct Nordic BLE implementation.

For the receive-only Feather path, the repository now treats the `feather_nrf52840_express` as the USB-host microcontroller and expects an external `nRF24L01+` frontend for the actual FlowToy-compatible RF link. The new driver bundle lives in `drivers/flowtoy_bridge/`, with a CircuitPython schema harness for CI plus a manual Arduino sketch for live receive tests.

On the Heart side, the radio peripheral now models two concerns:

1. Receive raw packets from a newline-delimited JSON serial stream and publish them as normalized `RadioPacket` events.
1. Send Flowtoys bridge commands back over the same serial link using typed helpers for sync, wake, power, Wi-Fi, global config, and pattern updates.

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

The current Heart integration deliberately stops at the serial bridge boundary. It does not attempt direct host control of an `nRF24L01` or an `nRF52840`. If the hardware path changes later, `RadioDriver` is the seam to swap while keeping the `RadioPeripheral` receive and command APIs stable.
