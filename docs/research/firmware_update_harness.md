# Firmware update harness: configuration validation and file handling

## Summary

The firmware update harness in `src/heart/manage/update.py` now validates driver
settings early, ensures required driver files exist before mounting devices, and
uses portable filesystem operations in place of shell `cp`/`rm` calls. These
changes reduce partial updates when settings are malformed or driver assets are
missing, and they improve error messages for maintenance workflows.

## Materials

- `src/heart/manage/update.py`

## Notes

- `DriverConfig` centralizes parsing of `settings.toml` keys so missing values
  fail fast with a clear list of required keys.
- `_ensure_driver_files` verifies `boot.py`, `code.py`, and `settings.toml`
  before any device copy steps, reducing partially configured devices.
- `copy_file` and `load_driver_libs` now rely on `shutil` to keep filesystem
  operations portable and reduce reliance on shell subprocesses.
