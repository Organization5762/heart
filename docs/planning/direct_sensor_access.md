# Direct Sensor Access Plan

## Problem Statement

Provide a reproducible path to interrogate hardware sensors from a host workstation without launching the full Heart runtime.

## Materials

- CircuitPython-compatible sensor boards connected over USB.
- Existing drivers under `drivers/` for the targeted sensors.
- Host workstation with Python 3.11, `pyserial`, and access to the repository.
- USB cable capable of data transfer.

## Opening Abstract

We need a tooling flow that lets engineers and manufacturing technicians query a sensor board directly. The current runtime requires the entire game loop to boot before peripherals respond, slowing diagnosis and automated QC. This plan outlines a split design: lightweight CircuitPython probe scripts flashed to the board and a host CLI that streams responses. By standardising the interface, we can reuse the same scripts for lab validation, line-side checks, and regression tests.

### Why Now

Upcoming driver revisions introduce new sensors whose behaviour must be verified before integration. Establishing a direct-access workflow reduces turnaround time between hardware iterations and prevents regressions from slipping into the runtime.

## Success Criteria

| Behaviour | Signal | Owner |
| --- | --- | --- |
| Board responds to probe command without the runtime | Host CLI receives a structured payload within 2 seconds | Firmware maintainer |
| Operators can select any supported sensor by module path | CLI `--sensor` flag resolves to the correct CircuitPython module | Tooling engineer |
| QC run emits archived artefacts | Probe session writes a timestamped log to `docs/debugging/logs/` | Manufacturing lead |

## Task Breakdown Checklists

### Discovery

- [ ] Audit existing drivers for dependencies beyond the CircuitPython standard library.
- [ ] Catalogue serial port identifiers for supported boards on macOS, Linux, and Windows.
- [ ] Document current flashing workflow and pain points.

### Implementation

- [ ] Add `drivers/utils/probe_base.py` with argument parsing and read loop helpers.
- [ ] Create per-sensor `probe.py` scripts subclassing the base helper.
- [ ] Implement `scripts/sensor_probe.py` with flags for sensor selection, serial device, and optional recording.
- [ ] Provide automated flashing helper `scripts/flash_board.py` that copies UF2 images and selected probes.

### Validation

- [ ] Execute probes for accelerometer and heart-rate sensors, capturing sample logs.
- [ ] Run probe sessions on macOS and Linux workstations to confirm cross-platform behaviour.
- [ ] Add smoke tests that exercise the host CLI against a simulated serial port to guard the interface contract.

## Narrative Walkthrough

Discovery focuses on understanding driver footprints and host OS quirks so the tooling accounts for serial naming conventions and memory limits. Implementation builds two cooperating layers: CircuitPython probes that expose a minimal API and a host CLI that orchestrates flashing, command dispatch, and logging. Validation closes the loop by running probes across platforms, collecting artefacts, and introducing automated tests that simulate board responses. This sequencing ensures we only invest in tooling once the constraints are known and that every feature is immediately exercised.

## Visual Reference

| Layer | Responsibility | Key Modules |
| --- | --- | --- |
| CircuitPython probe | Initialise sensor, emit JSON payloads, respond to `ping` command | `drivers/utils/probe_base.py`, `drivers/<sensor>/probe.py` |
| Host CLI | Flash probe, open serial port, stream and optionally persist readings | `scripts/flash_board.py`, `scripts/sensor_probe.py` |
| QC Automation | Aggregate logs and raise failures on out-of-range readings | `docs/debugging/logs/`, CI harness |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning |
| --- | --- | --- | --- | --- |
| CircuitPython storage limits block multiple probes | Medium | Medium | Generate probe scripts from templates and copy only the requested sensor | Flash process reports out-of-space errors |
| Serial port differences across OS cause connection failures | Medium | High | Provide configuration file with known port patterns and allow explicit override | CLI logs retries with enumerated device list |
| Probes drift from runtime behaviour | Low | High | Share parsing utilities between runtime drivers and probes | Unit tests fail when shared helpers diverge |

### Mitigation Tasks

- [ ] Implement template generation for probes so optional modules stay off the board.
- [ ] Add OS-specific serial detection logic with overrides.
- [ ] Extract shared parsing code into a common module used by both runtime and probe scripts.

## Outcome Snapshot

Technicians can flash a board, run a single CLI command, and receive structured sensor readings plus archived logs in under two minutes. Developers reuse the same tooling for regression tests, and probe scripts share code with the runtime so behaviour stays aligned.
