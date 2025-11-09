# Radio Bridge Firmware Stub

This directory contains a CircuitPython runtime that streams raw radio packets to
Heart over the USB serial console. The firmware currently emits empty payloads
so the host pipeline can be validated before the real transceiver is wired in.

## File overview

| File | Purpose |
| ---- | ------- |
| `code.py` | Main loop. Polls the radio interface (stubbed for now) and prints newline-delimited JSON packets with the `peripheral.radio.packet` event type. |
| `boot.py` | Reserved for any board-specific boot customisation. Currently blank. |
| `settings.toml` | Place holder for CircuitPython workflow metadata such as supported board IDs. Update this once the bridge hardware is selected. |

## Output format

Each iteration prints a single JSON object terminated by a newline. The object
contains the event type and a `data` mapping. When real hardware is attached the
data mapping should include decoded payload bytes, frequency, RSSI, and any
other telemetry required by `SerialRadioDriver`.

```json
{"event_type": "peripheral.radio.packet", "data": {}}
```

Upload this firmware to the chosen microcontroller and connect it to the host
with USB. Configure Heart with `HEART_RADIO_PORT=/dev/ttyXYZ` (use a comma-
separated list for multiple receivers) so the new radio peripheral can discover
the bridge automatically.
