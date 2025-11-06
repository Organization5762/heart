# Direct Sensor Access Plan

Goal: allow developers to interrogate a hardware sensor from the host machine without launching the full game runtime. The tool should stream readings over USB serial and expose a thin API for automated tests.

## Requirements

- **Board connection**: reuse the existing CircuitPython USB serial channel.
- **Selectable sensors**: support choosing a sensor by module path (e.g., `drivers.sensors.imu`).
- **Minimal dependencies**: run under CircuitPython with only built-in modules plus our driver.
- **Host-side convenience**: provide a Python CLI in `scripts/` that sends commands and prints parsed readings.
- **Automated quality check (QC)**: make it effortless to flash a new board, confirm the sensor responds, and record a short
  diagnostic trace without manual intervention.

## Proposed flow

1. **Probe script template**
   - Add `drivers/utils/probe_base.py` with a helper class that handles argument parsing from `sys.argv` and loops over reads.
   - Each sensor provides a `probe.py` that subclasses the helper and implements `read_once()`.
1. **Host CLI**
   - Create `scripts/sensor_probe.py` that opens the board serial port, flashes the requested `probe.py`, and streams the responses.
   - Support a `--record` flag to write samples to disk for offline analysis.
1. **Documentation & examples**
   - Extend `docs/debugging/circuitpython_peripherals.md` with instructions for running the probes.
   - Ship one example (e.g., accelerometer) to validate the flow.

## Automated QC happy-path

1. **Automated flashing**: wrap the UF2 copy procedure in a `scripts/flash_board.py` helper so CI or a developer can reset a
   board and load the probe script with a single command.
1. **Connectivity verification**: after flashing, issue a lightweight `ping` command over serial that expects a known response
   (for example, firmware version plus sensor ID). Fail fast if the response is absent or malformed.
1. **Sensor self-test**: run the associated `probe.py` in a bounded loop (e.g., 10 samples) and assert that the readings fall
   within expected sanity ranges defined per sensor.
1. **Report aggregation**: persist the flash log, ping outcome, and sample statistics to `docs/debugging/logs/` so hardware can
   be baselined over time and regressions are obvious.

Keeping this QC path automated and low-friction is critical—every fresh board flash should produce a deterministic pass/fail
signal within seconds so driver regressions are caught before they reach the wider runtime.

## Open questions

- How do we bundle per-sensor dependencies without filling the board storage? Possibly generate probes on the fly from templates.
- Should the host CLI support live plotting (e.g., matplotlib) or stay text-only initially?
