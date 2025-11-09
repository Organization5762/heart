# Problem Statement

The runtime now exposes a unified keyed-metric scaffold in [`src/heart/events/metrics.py`](../../src/heart/events/metrics.py), yet the observability backlog lacks a catalog that groups loop, peripheral, and renderer metrics by their operational purpose. Without a roadmap that ties each metric family to the new scaffold, implementation teams risk shipping ad-hoc observers, missing prerequisites such as Fast Fourier Transform (FFT) helpers, and leaving the future telemetry exporter without consistent payloads.

# Materials

- Access to the Heart repository with focus on `src/heart/events/metrics.py`, `src/heart/utilities/metrics.py`, and the event bus surfaces under `src/heart/peripheral/core/event_bus.py`.
- Python 3.11 toolchain managed through `uv`, plus `make` targets for formatting (`make format`) and validation (`make test`).
- Sample trace data from accelerometer, gyroscope, microphone, infrared, and UWB peripherals stored under `drivers/` fixtures and `experimental/` capture scripts.
- Numerical processing libraries already vendored or approved for inclusion (NumPy, SciPy) to cover FFT, Hilbert transforms, and rolling statistics.
- Diagramming capability (Mermaid or lightweight table tooling) to document scaffold mappings and signal cadences.

# Opening Abstract

This roadmap enumerates the metrics required for the next observability push and aligns them with the keyed-metric scaffold already in the codebase. Metrics are organised into runtime performance, peripheral health, environment and ambient sensing, and program responsiveness categories so that each team can prioritise the signals most relevant to their domain. For every metric family we summarise purpose, domain relevance, prerequisites, and how the new scaffold should represent state, cadence, and snapshot formats. Cross-references to existing modules and test locations ensure that future implementations slot directly into established utilities without duplicating data plumbing.

# Success Criteria

| Goal | Validation Signal | Owner |
| --- | --- | --- |
| Publish category-aligned metric specifications with scaffold mapping | Document merged with coverage checklist linked in `docs/planning/README.md` | Observability lead |
| Land reusable processing helpers (FFT, Hilbert envelopes, window filters) | Unit tests under `tests/events/metrics/` and `tests/utilities/` covering helper accuracy | Runtime maintainer |
| Wire priority metrics into exporter prototypes | Telemetry snapshots emitted through `src/heart/utilities/metrics.py` during staging runs | Runtime maintainer |
| Capture validation data sets for each metric category | Fixture updates stored under `drivers/fixtures/metrics/` with provenance notes | QA engineer |

# Task Breakdown

## Discovery

- [ ] Audit current metric usage in `src/heart/events/metrics.py` and `src/heart/utilities/metrics.py` to confirm existing primitives.
- [ ] Inventory signal emitters in `src/heart/peripheral` and `src/heart/environment.py` to identify data availability for each category.
- [ ] Collect representative traces (motion, audio, RF, environmental) and store them under a shared `drivers/fixtures/metrics/` namespace with README annotations.
- [ ] Review exporter interfaces (`src/heart/utilities/telemetry.py`) to understand payload constraints and required schema fields.

## Implementation

- [ ] Define keyed-metric subclasses for each category using rolling window policies in `src/heart/events/metrics.py`.
- [ ] Introduce shared signal processing helpers (FFT, Hilbert transform, envelope followers) under `src/heart/utilities/signal.py` with pure-Python fallbacks.
- [ ] Extend peripheral publishers (accelerometer, IR array, microphone, UWB) to feed the new metrics through `EventBus.observe()` hooks.
- [ ] Update the telemetry exporter to include scaffold snapshot metadata (window bounds, cadence hints) inside emitted payloads.

## Validation

- [ ] Add regression tests in `tests/events/metrics/` covering snapshot immutability, window pruning, and derived signal accuracy for each metric.
- [ ] Create integration tests simulating multi-stream ingestion via `tests/peripheral/test_event_bus_metrics.py` to validate concurrency behavior.
- [ ] Replay captured traces with `scripts/peripheral/replay_events.py` and compare emitted aggregates against documented success thresholds.
- [ ] Run `make test` and `make format` prior to landing changes.

# Narrative Walkthrough

Discovery begins with a deep dive into the existing keyed-metric implementations to verify which primitives already deliver rolling windows, counters, and percentile calculations. The audit reveals how `EventWindow`, `MaxAgePolicy`, and `MaxLengthPolicy` are currently applied so that new metrics can reuse the same pruning semantics. Simultaneously, we map each peripheral or runtime module that will supply source data—`src/heart/peripheral/motion/` for IMU vectors, `src/heart/peripheral/audio/microphone.py` for loudness levels, `src/heart/environment.py` for scheduler state, and renderer timing hooks inside `src/heart/renderer/core.py`. Annotated traces pulled into `drivers/fixtures/metrics/` provide the baseline data sets required for verifying FFT-derived amplitudes or Hilbert envelopes without live hardware.

During implementation we define category-specific metric classes that inherit from `KeyedMetric`. Runtime performance metrics (loop latency, queue depth) lean on monotonic timestamp deltas captured via `EventBus.monotonic()` and scheduler hooks, while peripheral health metrics aggregate device-specific payloads like accelerometer vectors or UWB range samples. Environment metrics consume slower cadences such as temperature or CO₂ levels, and program responsiveness metrics observe renderer frame outputs and playlist transitions. Each class documents the expected `snapshot()` schema so exporters can pass data through without schema guesswork. Signal processing prerequisites live beside other utilities under `src/heart/utilities/`, guarding advanced transforms behind availability checks and property tests. Peripheral publishers are updated to funnel raw observations into the shared metrics, ensuring no per-device duplication of rolling logic.

Validation closes the loop by emphasising reproducibility. For each category we craft deterministic unit tests that feed synthetic but well-understood inputs into the metrics, confirming that pruning policies yield the right cardinality and that derived values (e.g., FFT magnitude peaks) match reference results within tolerance. Integration tests simulate concurrent event streams to ensure keyed snapshots remain thread-safe and to verify that the exporter preserves cadence metadata. Replay scripts run across captured traces, generating JSON snapshots archived alongside the fixtures so QA can diff new results when dependencies change. A final pass through `make test` and `make format` keeps linting and style consistent.

# Visual Reference

| Category | Metric Families | Purpose & Domain Relevance | Prerequisites | Scaffold Mapping |
| --- | --- | --- | --- | --- |
| Runtime Performance | Event loop latency, queue depth histogram, render frame time percentiles, garbage collection pauses | Quantifies scheduler health for `src/heart/loop.py` and ensures renderers under `src/heart/renderer/` meet frame budgets | Access to monotonic timestamps, GC hooks, optional psutil for memory sampling | **State:** global loop counters and renderer tick IDs. **Cadence:** 100 ms loop snapshots with per-frame deltas. **Snapshot:** `{"loop_latency_ms": float, "frame_p99_ms": float, "queue_depth_hist": dict}` |
| Peripheral Health | Accelerometer jerk RMS, gyroscope drift, heart-rate HRV, IR array confidence, UWB range residuals | Validates sensor accuracy and readiness; feeds diagnostics in `src/heart/peripheral/*` modules | Finite difference helpers, quaternion normalisation, Hilbert transform for envelope detection, per-device calibration tables | **State:** keyed by peripheral ID with rolling windows (5–20 s). **Cadence:** event-driven with min 50 ms stride. **Snapshot:** tuple mappings `{peripheral_id: {"jerk_rms": float, ...}}` |
| Environment & Ambient | Temperature trend, humidity dew point deviation, CO₂ excursion duration, acoustic noise floor | Tracks external conditions influencing program behaviour and user comfort | Exponential moving averages, optional FFT for band-limited noise, integration with `src/heart/peripheral/environment/` sensors | **State:** keyed environment channels with both raw and smoothed values. **Cadence:** 5 s updates aggregated into 5 min windows. **Snapshot:** layered dict storing raw sample, EMA, excursion counters |
| Program Responsiveness | Playlist transition latency, scene load duration, effect trigger success rate, command queue backlog | Ensures higher-level programs under `src/heart/programs/` respond within expected SLA; critical for interactive scenes | Access to event bus hooks, timestamp correlation, idempotent counters, optional diff-based snapshot compressor | **State:** keyed by program and playlist handle. **Cadence:** on transition events plus 1 s heartbeat. **Snapshot:** includes timestamp arrays `{program: {"transition_latency_ms": list, "command_backlog": int}}` |

# Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Signal |
| --- | --- | --- | --- | --- |
| Signal processing helpers introduce heavy dependencies or performance regressions | Medium | High | Provide pure-Python baseline with optional accelerated path; benchmark via `pytest --benchmark-only` | Increased loop latency or CI timeouts during helper tests |
| Metrics drift between documentation and implementation | Medium | Medium | Add schema assertions in `tests/events/metrics/test_catalog_contract.py` comparing docs to emitted payloads | Contract test failures or Grafana panels showing `NaN` values |
| Snapshot cadence mismatched with exporter expectations | Low | High | Encode cadence metadata in snapshots and validate via integration tests hitting `src/heart/utilities/telemetry.py` | Telemetry consumers logging cadence mismatch warnings |
| Replay fixtures diverge from production data characteristics | Low | Medium | Schedule quarterly refresh of fixtures and maintain provenance metadata | QA reports mismatched thresholds during validation |

## Mitigation Checklist

- [ ] Implement benchmark coverage for new helpers to cap per-sample processing time.
- [ ] Embed schema version fields inside each snapshot and enforce upgrades via CI checks.
- [ ] Document fixture provenance in `drivers/fixtures/metrics/README.md` and automate refresh reminders.
- [ ] Coordinate with observability owners to align exporter cadence expectations before rollout.

# Outcome Snapshot

Once this roadmap is executed, every metric category shares the keyed scaffold, exporting consistent snapshots that encode cadence and state metadata. Teams extending peripherals or runtime loops will reach for the documented classes rather than duplicating logic, and staged deployments will emit telemetry with reproducible fixtures for regression comparison. Exporters and dashboards can rely on stable schemas, while FFT and Hilbert prerequisites unlock richer signal analyses without ad-hoc scripts.
