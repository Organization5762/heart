# Driver update helper modules

## Problem statement

Summarize the refactor that splits the driver update workflow into focused helper modules, while keeping `packages/heart-device-manager/src/heart_device_manager/update.py` as the CLI entrypoint orchestrator.

## Materials

- `packages/heart-device-manager/src/heart_device_manager/update.py`.
- `packages/heart-device-manager/src/heart_device_manager/driver_update/configuration.py`.
- `packages/heart-device-manager/src/heart_device_manager/driver_update/downloads.py`.
- `packages/heart-device-manager/src/heart_device_manager/driver_update/filesystem.py`.
- `packages/heart-device-manager/src/heart_device_manager/driver_update/mounts.py`.
- `packages/heart-device-manager/src/heart_device_manager/driver_update/paths.py`.

## Notes

- Configuration parsing now lives in `configuration.py`, including the `DriverConfig` dataclass and TOML validation.
- Download logic, checksum verification, and network tooling remain in `downloads.py` to keep update orchestration focused.
- Filesystem operations (driver file validation, copying, and library staging) live in `filesystem.py`.
- Mount discovery, UF2 install orchestration, and CircuitPython volume updates are handled by `mounts.py`.
- Path resolution for the drivers directory and removable media roots is centralized in `paths.py`.
- `packages/heart-device-manager/src/heart_device_manager/update.py` wires the helpers together, preserving the existing entrypoint and error surface.
