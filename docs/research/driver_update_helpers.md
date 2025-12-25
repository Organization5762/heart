# Driver update helper modules

## Problem statement

Summarize the refactor that splits the driver update workflow into focused helper modules, while keeping `src/heart/manage/update.py` as the CLI entrypoint orchestrator.

## Materials

- `src/heart/manage/update.py`.
- `src/heart/manage/driver_update/configuration.py`.
- `src/heart/manage/driver_update/downloads.py`.
- `src/heart/manage/driver_update/filesystem.py`.
- `src/heart/manage/driver_update/mounts.py`.
- `src/heart/manage/driver_update/paths.py`.

## Notes

- Configuration parsing now lives in `configuration.py`, including the `DriverConfig` dataclass and TOML validation.
- Download logic, checksum verification, and network tooling remain in `downloads.py` to keep update orchestration focused.
- Filesystem operations (driver file validation, copying, and library staging) live in `filesystem.py`.
- Mount discovery, UF2 install orchestration, and CircuitPython volume updates are handled by `mounts.py`.
- Path resolution for the drivers directory and removable media roots is centralized in `paths.py`.
- `src/heart/manage/update.py` wires the helpers together, preserving the existing entrypoint and error surface.
