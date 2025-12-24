# Runtime layout and IO observability research note

## Context

The runtime now supports layout configuration without code edits and adds
visibility into high-volume IO paths. These changes reduce startup risk when
panel geometry varies and make BLE, sensor, and display frame traffic easier to
monitor during integration.

## Materials

- Heart runtime configuration via environment variables.
- Logging control via `HEART_LOG_RULES` and `HEART_LOG_DEFAULT_INTERVAL`.
- Source references listed below.

## Findings

- Layout configuration is driven by `HEART_DEVICE_LAYOUT`,
  `HEART_LAYOUT_COLUMNS`, and `HEART_LAYOUT_ROWS`. Panel pixel dimensions come
  from `HEART_PANEL_COLUMNS` and `HEART_PANEL_ROWS`.
- BLE UART parsing now drains multiple JSON frames per callback and reports
  byte/message counters through the logging controller.
- The LED matrix peripheral publishes frames as an observable stream and logs
  frame cadence for monitoring pipelines.
- Serial accelerometer reads use line-based reads with timeouts, salvage JSON
  payloads that contain preamble bytes, and log decode failures for debugging.
- Game mode registration initializes renderers immediately once navigation is
  ready, avoiding initialization races when new scenes are registered late.

## Operational guidance

- Use `HEART_DEVICE_LAYOUT=rectangle` for non-cube deployments and ensure layout
  and panel dimensions match the physical rig.
- Tune log sampling with `HEART_LOG_RULES` to surface BLE/sensor/display stats
  without spamming the console (for example,
  `HEART_LOG_RULES="ble.uart.poll=5:INFO,peripheral.display.frame=2:INFO"`).
- Watch `sensor.serial.poll` to confirm incoming sensor payload volume and
  decode error trends during bring-up.

## References

- `src/heart/utilities/env.py`
- `src/heart/device/selection.py`
- `src/heart/device/rgb_display/device.py`
- `src/heart/peripheral/bluetooth.py`
- `src/heart/peripheral/led_matrix.py`
- `src/heart/peripheral/sensor.py`
- `src/heart/navigation.py`
