# Device Manager and Firmware IO package split

## Summary

Moved the former `heart.manage` and `heart.firmware_io` modules into dedicated
packages so they can be versioned and published independently of the main
runtime. The root `heart` package now consumes them through local `uv` path
dependencies during development.

## Materials

- `packages/heart-device-manager/pyproject.toml`
- `packages/heart-device-manager/src/heart_device_manager/update.py`
- `packages/heart-device-manager/src/heart_device_manager/driver_update/paths.py`
- `packages/heart-firmware-io/pyproject.toml`
- `packages/heart-firmware-io/src/heart_firmware_io/bluetooth.py`
- `src/heart/cli/commands/update_driver.py`
- `src/heart/peripheral/input_payloads/radio.py`
- `drivers/sensor_bus/code.py`
- `pyproject.toml`

## Notes

- `heart-device-manager` now owns the driver update workflow and carries its
  own logging and environment helpers so the package does not depend on the
  main runtime.
- `heart-firmware-io` now owns the shared CircuitPython-facing helpers that
  device drivers import directly.
- The root `heart` package depends on both new distributions through
  `tool.uv.sources`, which keeps local development editable while preserving
  separate package metadata and import roots.
- Driver and runtime imports were updated from `heart.manage` and
  `heart.firmware_io` to `heart_device_manager` and `heart_firmware_io`.
