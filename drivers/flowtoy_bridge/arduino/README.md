# Native FlowToy Firmware

These sketches are the real radio-facing side of the FlowToy bridge. The
CircuitPython `code.py` driver in the parent directory remains useful for the
serial contract and host tooling, but actual FlowToy packet capture on a
`feather_nrf52840_express` currently requires native firmware.

## Available sketches

| Path | Target | Notes |
| ---- | ------ | ----- |
| `flowtoy_feather_nrf52840_receiver/flowtoy_feather_nrf52840_receiver.ino` | `feather_nrf52840_express` internal 2.4 GHz radio | Preferred path when using only the Feather. Uses the `nrf_to_nrf` Arduino library to emulate the RF24-style link used by the upstream Flowtoys bridge. |

## Arduino dependencies

- Adafruit nRF52 board support package for Arduino
- `nrf_to_nrf` by TMRh20

## Flashing notes

1. Select `Adafruit Feather nRF52840 Express` in Arduino IDE.
2. Install the `nrf_to_nrf` library from Library Manager.
3. Open the sketch above and flash it to the board.
4. Read the USB serial port at `115200` baud.

The sketch listens on Flowtoys' known RF parameters and emits the same
newline-delimited JSON schema used by the host-side `flowtoy_bridge` driver.

If you prefer the repo tooling, `totem update-driver --name flowtoy_bridge`
now uses this native path by default. The manual Arduino flow remains useful for
iterating on the sketch directly.
