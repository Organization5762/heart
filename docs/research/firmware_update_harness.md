# Firmware update harness: configuration validation and file handling

## Summary

The firmware update harness in `src/heart/manage/update.py` validates driver
settings early, accepts both list and comma-delimited formats for driver
libraries and board IDs, and confirms the media mount root exists before
searching for CircuitPython volumes. These checks reduce partial updates when
settings are malformed or removable storage is missing, while improving error
messages for maintenance workflows.

## Materials

- `src/heart/manage/update.py`

## Notes

- `DriverConfig` centralizes parsing of `settings.toml` keys so missing values
  fail fast with a clear list of required keys.
- `_parse_csv` now supports TOML list values alongside comma-separated strings,
  keeping `CIRCUIT_PY_DRIVER_LIBS` and `VALID_BOARD_IDS` flexible for future
  driver settings.
- `_mount_points` validates the media root early and narrows the search to
  directories, so missing volumes produce actionable errors before any file
  copies begin.
