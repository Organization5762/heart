# Problem Statement

The aggregate metrics pipeline for sensor peripherals lacks regression coverage and published targets, which makes it difficult to confirm that rolling windows, keyed statistics, and downstream dashboards behave consistently as we integrate new devices.

# Materials

- Python 3.11 toolchain with `uv` environment defined in `pyproject.toml`.
- Access to the Heart repository, especially `src/heart/events/metrics.py` and `tests/events/metrics/`.
- Local runtime capable of executing `make test` and `make format`.
- Historical sensor traces stored in `drivers/` fixtures for offline validation.
- Diagramming tool (Mermaid or Excalidraw) for sequence sketches.

# Opening Abstract

This plan extends regression coverage for the aggregate metrics helpers and defines a roadmap for collecting richer telemetry from accelerometer, gyroscope, heart-rate, infrared, UWB, and environmental sensors. By grounding every metric in rolling windows backed by deterministic tests, the team can ship sidecar aggregators and UI dashboards without re-implementing statistics logic in each component. The proposal sequences work so that we harden the Python primitives, align on a library of reusable aggregates, then wire metrics into orchestration layers and Grafana exports.

# Success Criteria

| Goal | Validation Signal | Owner |
| --- | --- | --- |
| Expand tests for `RollingStatisticsByKey` and related helpers | New pytest cases in `tests/events/metrics/` covering resets, window+length pruning, and policy composition | Application engineer |
| Publish metrics catalog for all sensor families | Planning doc merged with enumerated aggregates, thresholds, and sampling guidance | Sensor lead |
| Validate aggregator outputs on real traces | Replay logs through `scripts/peripheral/replay_events.py` and confirm metrics fall within documented thresholds | QA engineer |
| Integrate aggregates into telemetry bus | `EventBus` emits derived metrics for accelerometer, IR, microphone, and UWB peripherals with schema notes | Runtime maintainer |

# Task Breakdown

## Discovery

- [ ] Review existing usages of `RollingStatisticsByKey` within `experimental/peripheral_sidecar/`.
- [ ] Audit Grafana dashboards to determine which aggregates already exist.
- [ ] Collect sample traces from accelerometer, heart-rate, IR array, and UWB peripherals.

## Implementation

- [ ] Add targeted regression cases for resets, mixed pruning policies, and missing-key handling in `tests/events/metrics/`.
- [ ] Introduce helper fixtures for ingesting sensor traces into rolling windows.
- [ ] Wire aggregate emitters into accelerometer, heart-rate, microphone, IR array, and UWB pipelines.
- [ ] Document metric schemas inline and export via `docs/library/runtime_systems.md`.

## Validation

- [ ] Run `make test` and ensure deterministic results on Linux and macOS runners.
- [ ] Execute trace replays to confirm metric values align with catalog thresholds.
- [ ] Update Grafana dashboards or CLI reporters to consume the new metrics.
- [ ] Conduct code review focusing on numerical stability and timestamp handling.

# Narrative Walkthrough

We start with a focused test suite expansion to ensure the aggregate metrics helpers handle resets, sparse keys, and overlapping pruning policies. These utilities currently back the experimental sidecar aggregators, so coverage will prevent regressions when telemetry sources multiply. After the tests, we design a catalog that maps each sensor family to the aggregates we expect to compute. The catalog acts as the contract for downstream consumers, clarifying sampling windows, threshold logic, and naming conventions.

Next, we augment the accelerometer, heart-rate, IR sensor array, microphone, and UWB modules to publish the documented aggregates. Where hardware is not yet streaming live data, replay scripts and recorded traces validate the behavior. Finally, the telemetry bus and dashboards are updated to consume the enriched events, ensuring observability teams receive consistent payloads regardless of the originating sensor.

# Visual Reference

| Sensor Family | Aggregate Metrics | Sampling Window | Notes |
| --- | --- | --- | --- |
| Accelerometer | magnitude RMS, jerk mean, jerk stddev, orientation change count, vibration percentile, zero-crossing rate, tilt dwell time, impact peak, sway ellipse area, motion energy | 5 s rolling window with 0.5 s stride | Derived from `AccelerometerVector` events; jerk computed from finite differences |
| Gyroscope | angular velocity mean, angular velocity stddev, drift bias, yaw variance, pitch/roll RMS, spin rate histogram, stabilization confidence | 10 s window with 1 s stride | Combines bus events once gyroscope virtual peripheral lands |
| Magnetometer | heading variance, hard-iron offset, soft-iron scaling stability, geomagnetic disturbance flag | 30 s window with 5 s stride | Requires calibration offsets stored per producer |
| Heart-rate | beats-per-minute average, HRV RMSSD, tachycardia count, bradycardia minutes, signal quality index, perfusion index trend | 60 s window sliding every 5 s | Leverages `heart.peripheral.heart_rates` data frames |
| IR Sensor Array | position RMSE, confidence mean, amplitude histogram, sensor dropout count, multipath suspicion score, ambient temperature delta, calibration drift | per-frame aggregation plus 15 s rolling summary | Mixes per-frame outputs from `IRSensorArray.EVENT_FRAME` |
| UWB | range residual stddev, anchor availability, blink density, latency percentile, NLOS suspicion counter, spatial consistency score | 20 s window with 2 s stride | Consumes `uwb_ranging_event` logs |
| Microphone | RMS level mean, peak level max, noise floor trend, clipping count, speech probability estimate, spectral centroid | 8 s window with 1 s stride | Extend `MicrophoneLevel` payloads with frequency features |
| Environmental (temp, humidity, CO₂) | mean, rate of change, excursion duration, dew point deviation, alarm threshold breaches | 5 min window with 30 s stride | Aggregates future environmental peripherals |
| Switch / Button | press frequency, long-press duration mean, rotation cumulative delta, inactivity streak length | 60 s window with event-driven updates | Derived from firmware input events |

# Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Signal |
| --- | --- | --- | --- | --- |
| Timestamp drift between sensors causes inaccurate rolling windows | Medium | High | Normalize timestamps via `EventBus.monotonic()` and align on sync protocol | Divergent window counts across test runs |
| Metric catalog diverges from emitted payloads | Medium | Medium | Enforce schema tests comparing docs to event outputs | Failing contract tests during CI |
| Numerical instability for low-variance sensors | Low | Medium | Clamp variances to zero and add property-based tests | Negative variance observed in logs |
| Performance regression from heavy aggregations | Low | High | Profile replay scripts and move expensive stats to native modules when needed | Increased CPU usage during sidecar benchmarks |

## Mitigation Checklist

- [ ] Implement timestamp normalization helper shared across peripherals.
- [ ] Add contract tests comparing emitted aggregates to the catalog table.
- [ ] Profile aggregator loops with representative traces and cache intermediate computations.
- [ ] Schedule quarterly review of metric catalog with data science and firmware teams.

# Outcome Snapshot

After executing this plan, the aggregate metrics helpers expose deterministic behavior through regression tests, every sensor family publishes the agreed metrics with consistent naming, and monitoring tooling consumes the enriched payloads without additional glue code. Replay pipelines produce stable rollups, giving operators confidence that new peripherals will integrate into the observability stack with minimal risk.
