# Debugging CircuitPython Peripheral Drivers

## Problem Statement

Iterate on CircuitPython-based drivers that back Heart peripherals while working within the RAM, storage, and tooling constraints of microcontroller boards.

## Materials

- Supported CircuitPython board with the latest UF2 firmware.
- USB connection for file transfer and serial REPL access.
- Required driver code from `drivers/` along with any third-party library bundles.
- Terminal tools such as `screen`, `minicom`, or `adafruit-ampy` for REPL access.

## Technical Approach

1. Prepare the board with the correct firmware and dependencies.
1. Develop and reload the driver in small, testable increments to avoid exhausting memory.
1. Capture sensor output and failure modes so issues can be reproduced without the board.

## Board Preparation

1. Flash the most recent CircuitPython image for the target board.
1. Copy the `lib/` dependencies and the driver under test to the board storage volume.
1. Open a serial REPL at the documented baud rate (usually `115200`).

## Driver Update Helper

When you use `heart`'s driver update helper (`src/heart/manage/update.py`), it will:

- Download the configured UF2 or CircuitPython bundle and verify its SHA-256 checksum.
- Skip optional `.mpy` bundle files that are not present in the bundle.
- Copy driver `code.py`, `boot.py`, and `settings.toml` into matching `CIRCUITPY` volumes.

## Iteration Practices

- Use `code.py` as an entry point so saving a file triggers an automatic reload.
- Keep scripts minimal to prevent memory exhaustion; remove optional helpers when debugging.
- Gate verbose logging behind constants (for example, `if DEBUG:`) to keep the REPL usable.

## Capturing Sensor Traffic

- Build focused probe scripts that initialise a single sensor, read a fixed number of samples, and print them.
- Record representative sessions and archive them in `docs/debugging/logs/` when they explain a regression.
- Use deterministic delays (`time.sleep(0.05)` or integer millisecond loops) to simplify trace comparison.

## Failure Handling

- If the board enters safe mode, remove the suspect driver, reset, and reintroduce components incrementally.
- Power-cycle the board when I2C or SPI buses wedge.
- Capture peripheral-specific quirks in driver docstrings as outlined in `drivers/AGENTS.md`.

## Desktop Reproduction Harness

Where practical, mirror the driver API with a desktop shim (for example, `drivers/i2c/some_sensor_sim.py`) so pytest can cover computational logic without the physical hardware.
