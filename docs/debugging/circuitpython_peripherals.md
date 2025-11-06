# Debugging CircuitPython Peripheral Drivers

CircuitPython targets microcontrollers with limited RAM, storage, and tooling. The tips below capture the workflow we use for iterating on drivers in `drivers/` and the supporting scripts that speak to the board over USB.

## Preparing the board

1. **Install the latest CircuitPython build** that supports the device. Adafruit publishes UF2 images for common boards.
1. **Copy the project bundle**: upload the `lib/` dependencies and the driver under test to the board's storage volume.
1. **Open a serial REPL** using `screen`, `minicom`, or the `adafruit-ampy` tooling. Set the baud rate published in the board manual (typically `115200`).

## Iterating on code

- **Hot reload with `code.py`**: save the driver to `code.py` or import it from a helper script. CircuitPython automatically restarts execution after the file write.
- **Keep scripts tiny**: the board restarts when memory is exhausted. Split optional helpers into separate files that can be deleted from the board when chasing bugs.
- **Toggle diagnostics via constants**: wrap verbose prints in `if DEBUG:` checks to avoid flooding the serial console.

## Capturing sensor traffic

- **Single-sensor probes**: write a `probe.py` script that only initializes the sensor under test, reads a handful of values, and prints them. This isolates hardware problems from the rest of the runtime.
- **Record sample sessions**: copy the serial output to a text file and check it into `docs/debugging/logs/` (or discard after investigating) so regressions are easier to spot.
- **Use deterministic timing**: avoid floating-point sleeps. Prefer `time.sleep(0.05)` or integer millisecond counters to make traces easier to compare.

## Handling failures

- **Hard crashes / safe mode**: if the board boots into safe mode, remove the offending driver, reset, and reintroduce pieces incrementally.
- **Bus lockups**: power-cycle the board and unplug other peripherals. Many I2C/SPI sensors need a full power reset to clear a wedged bus.
- **Peripheral-specific notes**: document any errata or quirks directly in the driver docstrings per the guidance in `drivers/AGENTS.md`.

## Desktop reproduction harness

When possible, mirror the driver API with a desktop shim (for example, `drivers/i2c/some_sensor_sim.py`) so pytest can exercise the core logic. This is invaluable when the only reproduction requires the real hardware.
