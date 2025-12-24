## Heart manage update workflow

The `src/heart/manage/update.py` helper updates CircuitPython driver devices with the
runtime `boot.py`, `code.py`, and `settings.toml` files stored in `drivers/<driver>`.
It also syncs the required CircuitPython libraries from the Adafruit bundle and the
`heart.firmware_io` package when requested.

### Materials

- A host machine with the Heart repository checked out.
- A CircuitPython-compatible device mounted under `/Volumes` (macOS) or
  `/media/michael` (Raspberry Pi), or another mount directory passed via `--media-dir`.
- A driver folder under `drivers/` containing `boot.py`, `code.py`, and
  `settings.toml` with valid firmware metadata.

### Usage

Run the script with the driver folder name:

```bash
python -m heart.manage.update <driver-folder-name>
```

Optional flags:

- `--media-dir`: Override the mount directory used to discover devices.
- `--skip-uf2`: Skip UF2 firmware installation even if a device is in boot mode.
- `--skip-libs`: Skip syncing the CircuitPython library bundle to the device.
- `--dry-run`: Log intended operations without copying files or downloading assets.

### Notes

- UF2 installation is only attempted when a device is detected in boot mode under the
  configured media directory.
- Driver settings are read from `drivers/<driver>/settings.toml` and must include the
  `CIRCUIT_PY_*` keys and `VALID_BOARD_IDS` list expected by the updater.
