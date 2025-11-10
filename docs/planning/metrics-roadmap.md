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

# Progress Update (2025-11-09)

| Completed Work | Evidence | Next Focus |
| --- | --- | --- |
| Keyed extrema, percentile, moment, and inter-arrival metrics implemented with pruning policies. | `src/heart/events/metrics.py` plus targeted coverage in `tests/events/metrics/test_advanced_metrics.py`. | Extend exporters to emit scaffold cadence metadata and hook peripheral publishers. |
| Signal and statistics helper suites for FFT, Hilbert envelopes, cross-correlation, histogram, and EWMA flows landed with validation. | `src/heart/utilities/metrics.py`, `src/heart/utilities/signal.py`, `src/heart/utilities/statistics.py`, and the regression suites in `tests/utilities/`. | Capture representative fixtures under `drivers/fixtures/metrics/` for long-horizon validation. |

# Task Breakdown

## Discovery

- [x] Audit current metric usage in `src/heart/events/metrics.py` and `src/heart/utilities/metrics.py` to confirm existing primitives.
- [ ] Inventory signal emitters in `src/heart/peripheral` and `src/heart/environment.py` to identify data availability for each category.
- [ ] Collect representative traces (motion, audio, RF, environmental) and store them under a shared `drivers/fixtures/metrics/` namespace with README annotations.
- [ ] Review exporter interfaces (`src/heart/utilities/telemetry.py`) to understand payload constraints and required schema fields.

## Implementation

- [x] Define keyed-metric subclasses for each category using rolling window policies in `src/heart/events/metrics.py`.
- [x] Introduce shared signal processing helpers (FFT, Hilbert transform, envelope followers) under `src/heart/utilities/signal.py` with pure-Python fallbacks.
- [ ] Extend peripheral publishers (accelerometer, IR array, microphone, UWB) to feed the new metrics through `EventBus.observe()` hooks.
- [ ] Update the telemetry exporter to include scaffold snapshot metadata (window bounds, cadence hints) inside emitted payloads.

## Validation

- [x] Add regression tests in `tests/events/metrics/` covering snapshot immutability, window pruning, and derived signal accuracy for each metric.
- [ ] Create integration tests simulating multi-stream ingestion via `tests/peripheral/test_event_bus_metrics.py` to validate concurrency behavior.
- [ ] Replay captured traces with `scripts/peripheral/replay_events.py` and compare emitted aggregates against documented success thresholds.
- [ ] Run `make test` and `make format` prior to landing changes. (Formatting currently blocked by offline dependency resolution; rerun once package index access is restored.)

# Narrative Walkthrough

Discovery begins with a deep dive into the existing keyed-metric implementations to verify which primitives already deliver rolling windows, counters, and percentile calculations. The audit reveals how `EventWindow`, `MaxAgePolicy`, and `MaxLengthPolicy` are currently applied so that new metrics can reuse the same pruning semantics. Simultaneously, we map each peripheral or runtime module that will supply source data—`src/heart/peripheral/motion/` for IMU vectors, `src/heart/peripheral/audio/microphone.py` for loudness levels, `src/heart/environment.py` for scheduler state, and renderer timing hooks inside `src/heart/renderer/core.py`. Annotated traces pulled into `drivers/fixtures/metrics/` provide the baseline data sets required for verifying FFT-derived amplitudes or Hilbert envelopes without live hardware.

During implementation we define category-specific metric classes that inherit from `KeyedMetric`. Runtime performance metrics (loop latency, queue depth) lean on monotonic timestamp deltas captured via `EventBus.monotonic()` and scheduler hooks, while peripheral health metrics aggregate device-specific payloads like accelerometer vectors or UWB range samples. Environment metrics consume slower cadences such as temperature or CO₂ levels, and program responsiveness metrics observe renderer frame outputs and playlist transitions. Each class documents the expected `snapshot()` schema so exporters can pass data through without schema guesswork. Signal processing prerequisites live beside other utilities under `src/heart/utilities/`, guarding advanced transforms behind availability checks and property tests. Peripheral publishers are updated to funnel raw observations into the shared metrics, ensuring no per-device duplication of rolling logic.

Validation closes the loop by emphasising reproducibility. For each category we craft deterministic unit tests that feed synthetic but well-understood inputs into the metrics, confirming that pruning policies yield the right cardinality and that derived values (e.g., FFT magnitude peaks) match reference results within tolerance. Integration tests simulate concurrent event streams to ensure keyed snapshots remain thread-safe and to verify that the exporter preserves cadence metadata. Replay scripts run across captured traces, generating JSON snapshots archived alongside the fixtures so QA can diff new results when dependencies change. A final pass through `make test` and `make format` keeps linting and style consistent.

# Metric Catalog

The tables below enumerate every metric family slated for implementation. Each row identifies the primary objective, prerequisites, scaffold integration strategy, cross-referenced utilities, and validation data that implementation teams must prepare.

## Spectral and Frequency-Domain Metrics

| Metric | Purpose & Domain Relevance | Prerequisites | Scaffold Integration | Cross References | Validation & Data Requirements |
| --- | --- | --- | --- | --- | --- |
| Spectral Centroid | Characterises perceived brightness in audio or vibration payloads for renderer tuning and anomaly detection. | FFT via `src/heart/utilities/signal.py::fft_magnitude`, Hann window helpers, cached spectrum buffers. | **State:** keyed by stream ID storing latest centroid value. **Cadence:** 20–50 ms frames from microphone and accelerometer publishers. **Snapshot:** `{ "centroid_hz": float, "window_size": int }`. | `src/heart/peripheral/audio/microphone.py`, `src/heart/peripheral/motion/imu.py`. | Use recorded chirps and broadband noise under `drivers/fixtures/metrics/audio/` with assertions in `tests/utilities/test_signal_fft.py`.
| Spectral Flatness (Wiener Entropy) | Differentiates tonal vs. noise-like segments for speech intelligibility and mechanical diagnostics. | FFT, log-domain safeguards, epsilon handling utilities. | **State:** maintains geometric and arithmetic mean caches per stream. **Cadence:** 50 ms sliding windows, hop size 25 ms. **Snapshot:** `{ "flatness_ratio": float }`. | `src/heart/utilities/statistics.py` for geometric means. | Validate against pure-tone and white-noise fixtures; compare to SciPy references in unit tests.
| Spectral Roll-off (95%) | Marks the frequency boundary capturing bulk energy to watch for muffled sensors or shifted harmonics. | FFT cumulative sum helper, configurable percentile constants. | **State:** retains cumulative energy array. **Cadence:** 100 ms windows for audio/IR sensors. **Snapshot:** `{ "rolloff_hz": float, "percentile": 0.95 }`. | `src/heart/events/metrics.py::PercentileMetric`. | Replay pink-noise sweeps and verify percentile outputs within tolerance envelopes.
| Spectral Entropy | Detects broadband randomness shifts in EEG/audio channels for fault triage. | Normalised FFT bins, log domain clamps. | **State:** store entropy scalars by channel. **Cadence:** 250 ms segments for EEG, 50 ms for audio. **Snapshot:** `{ "entropy_bits": float }`. | `src/heart/peripheral/neural/eeg.py`. | Synthetic impulses vs. uniform noise fixtures plus statistical expectation checks.
| Spectral Kurtosis / Kurtogram Peak | Flags narrow-band impulsive faults in rotating assets; critical for condition-based maintenance. | Filter bank generation, kurtosis calculator using `scipy.stats`, optional parallel FFT. | **State:** keyed by bearing ID with band index metadata. **Cadence:** order-synchronous windows aligned with RPM telemetry. **Snapshot:** `{ "peak_band_hz": float, "kurtosis": float }`. | `src/heart/peripheral/motion/vibration.py`, `src/heart/utilities/order_tracking.py`. | Validate using seeded bearing fault recordings stored in `drivers/fixtures/metrics/vibration/`.
| Envelope Spectrum Peak (Hilbert) | Surfaces demodulated fault lines (BPFO/BPFI) after Hilbert envelope extraction. | Hilbert transform helper (`src/heart/utilities/signal.py::hilbert_envelope`), band-pass filters. | **State:** retains dominant envelope peaks per shaft. **Cadence:** RPM-synchronous windows. **Snapshot:** `{ "envelope_peak_hz": float, "amplitude": float }`. | `src/heart/peripheral/motion/vibration.py`. | Compare against known bearing defect spectra; add regression fixtures to `tests/events/metrics/test_envelope.py`.
| Order-Tracked Amplitude/RMS | Measures energy at specific shaft orders to monitor mechanical balance and gear wear. | Tachometer alignment hooks, resampling utilities, RPM metadata ingestion. | **State:** keyed by order index; retains RMS amplitudes. **Cadence:** triggered on RPM updates plus 1 s heartbeat. **Snapshot:** `{ "order": int, "rms": float }`. | `src/heart/peripheral/motion/order_tracker.py`. | Use simulated rotor data with ramping RPM to confirm order tracking accuracy.
| Teager–Kaiser Energy Operator (TKEO) | Highlights instantaneous energy surges and impacts in EMG, speech, or vibration streams. | TKEO operator helper in `src/heart/utilities/signal.py`, derivative-friendly buffers. | **State:** stores instantaneous energy sequence with rolling mean. **Cadence:** sample-level streaming with decimated summaries (5 ms). **Snapshot:** `{ "tkeo_energy": list[float], "decimation": int }`. | `src/heart/peripheral/biopotential/emg.py`. | Validate with impulse trains and sine bursts; add tolerances in `tests/utilities/test_signal_tkeo.py`.
| Hjorth Parameters (Activity/Mobility/Complexity) | Provides compact morphology descriptors for EEG and biosignal monitoring to detect state transitions. | Rolling variance and derivative calculators, `numpy.gradient` wrappers. | **State:** stores tuple `(activity, mobility, complexity)` per channel. **Cadence:** 1 s windows with 50% overlap. **Snapshot:** `{ "activity": float, "mobility": float, "complexity": float }`. | `src/heart/peripheral/neural/eeg.py`. | Compare against MATLAB baselines using exported EEG traces.
| Fano Factor (Index of Dispersion) | Quantifies spike-train burstiness relative to Poisson expectations for neuroscience modules. | Event counting buffers, factorial moment helpers. | **State:** retains rolling event counts and variance. **Cadence:** 100 ms bins aggregated over 5 s. **Snapshot:** `{ "fano_factor": float, "window_events": int }`. | `src/heart/peripheral/neural/spike_detector.py`. | Use simulated Poisson vs. burst trains stored under `drivers/fixtures/metrics/neural/`.

## Standard Metrics (10)

| Metric | Purpose & Domain Relevance | Prerequisites | Scaffold Integration | Cross References | Validation & Data Requirements |
| --- | --- | --- | --- | --- | --- |
| Event Count | Baseline raw counts for loops, I/O events, or scheduler ticks. | Rolling counter helper in `src/heart/events/metrics.py`. | **State:** integer counter keyed by event type. **Cadence:** event-driven increments. **Snapshot:** `{ "count": int }`. | Event bus publishers in `src/heart/peripheral/core/event_bus.py`. | Synthetic event generators verifying monotonic increments.
| Event Rate (EPS) | Derives events per second to detect bursts or idling peripherals. | Sliding window counters, monotonic clocks. | **State:** stores cumulative count and window duration. **Cadence:** 1 s windows with 100 ms updates. **Snapshot:** `{ "eps": float }`. | `src/heart/events/metrics.py::RateMetric`. | Replay bursty traces; assert expected EPS in unit tests.
| Rolling Sum | Accumulates energy or tick values over sliding windows for energy budgeting. | Windowed sum helper, policy hooks. | **State:** maintains deque of values and total. **Cadence:** policy-driven (e.g., 5 s). **Snapshot:** `{ "sum": float, "window": float }`. | `src/heart/utilities/metrics.py`. | Inject deterministic value streams; confirm sums match manual integration.
| Rolling Min | Tracks lowest recent value to spot sags. | Windowed min heap structure. | **State:** retains min heap per key. **Cadence:** aligned with source cadence. **Snapshot:** `{ "min": float }`. | `src/heart/events/metrics.py::RollingExtrema`. | Validate using monotonic decreasing/increasing sequences.
| Rolling Max | Captures highest recent value for spike detection. | Same as Rolling Min but for max. | **State:** retains max heap. **Cadence:** source cadence. **Snapshot:** `{ "max": float }`. | `src/heart/events/metrics.py::RollingExtrema`. | Use sine wave fixtures verifying maxima tracking.
| Percentiles (p50/p90/p99) | Provides robust distribution insights for latency and sensor noise. | Ordered statistics buffer, `heapq` or `tdigest`. | **State:** stores percentile estimator state. **Cadence:** 1 s updates. **Snapshot:** `{ "p50": float, "p90": float, "p99": float }`. | `src/heart/events/metrics.py::PercentileMetric`. | Regression tests comparing to NumPy percentiles on stored traces.
| Histogram | Captures bucketed distribution snapshots for offline analysis. | Bucket definition utilities, aggregator arrays. | **State:** dictionary of bucket counts keyed by sensor ID. **Cadence:** 5 s windows. **Snapshot:** `{ "buckets": dict[str, int] }`. | `src/heart/utilities/metrics.py::Histogram`. | Validate via synthetic Gaussian vs. bimodal distributions.
| EWMA | Smooths noisy signals for dashboard readability. | Decay factor helpers, stable float accumulators. | **State:** retains last EWMA value. **Cadence:** matches sample cadence. **Snapshot:** `{ "ewma": float, "alpha": float }`. | `src/heart/utilities/filters.py`. | Compare to SciPy lfilter outputs using recorded telemetry.
| Merge Activity (Time-Decayed) | Highlights renderer merge pressure with recency weighting to tune binary vs. iterative fanout choices. | Time-decay metric helper with configurable decay curves. | **State:** timestamped merge contributions with 5 s horizon. **Cadence:** event-driven on each surface merge. **Snapshot:** `{ "decayed_value": float, "samples": int, "horizon_s": float, "decay_curve": str }`. | `src/heart/events/metrics.py::TimeDecayedActivity`, `src/heart/events/merge_activity.py::track_merge_activity`. | Validate via unit tests in `tests/events/metrics/test_time_decayed_activity.py` ensuring decayed totals follow linear and quadratic curves; cover instrumentation hooks in `tests/events/metrics/test_merge_activity_instrumentation.py`.
| Inter-Event Interval | Measures jitter between events to surface cadence drift. | Timestamp diff helpers, monotonic clock. | **State:** holds last timestamp, interval deque. **Cadence:** per-event updates. **Snapshot:** `{ "interval_ms": list[float] }`. | `src/heart/events/metrics.py::InterArrivalMetric`. | Feed deterministic intervals; assert jitter metrics inside tolerance.
| Threshold Exceedance Count | Tallies threshold breaches for alerting. | Comparator utilities, threshold configuration. | **State:** counts exceedances with reset policies. **Cadence:** per sample. **Snapshot:** `{ "breaches": int, "threshold": float }`. | `src/heart/utilities/metrics.py::ThresholdCounter`. | Use step functions crossing thresholds to validate counts.

## Unconventional / Experimental Metrics (5)

| Metric | Purpose & Domain Relevance | Prerequisites | Scaffold Integration | Cross References | Validation & Data Requirements |
| --- | --- | --- | --- | --- | --- |
| Z-Score (Anomaly Score) | Normalises deviation from rolling mean/std to flag anomalies across any scalar stream. | Rolling mean/variance calculator. | **State:** stores current z-score per key. **Cadence:** sample-synchronous. **Snapshot:** `{ "z_score": float }`. | `src/heart/utilities/statistics.py`. | Validate using Gaussian noise with injected outliers.
| Pattern Detection (CEP) | Detects complex event patterns (e.g., Konami sequences) for behavioural triggers. | Complex event processing DSL, state machine utilities. | **State:** retains automaton state. **Cadence:** event-driven. **Snapshot:** `{ "pattern_hits": int, "state": str }`. | `src/heart/events/patterns.py`. | Use scripted event sequences to assert state transitions.
| Cross-Correlation | Measures lag relationship between two streams, aiding alignment diagnostics. | Dual stream buffering, FFT-based correlation helper. | **State:** stores lag offsets and correlation score. **Cadence:** triggered on sliding window completion (e.g., 2 s). **Snapshot:** `{ "lag_ms": float, "correlation": float }`. | `src/heart/utilities/signal.py::cross_correlation`. | Compare against NumPy correlate on paired fixtures.
| Dominant Frequency (FFT) | Extracts strongest periodic component for oscillation tracking. | FFT magnitude sorting, window selection. | **State:** retains dominant bin and magnitude. **Cadence:** 200 ms windows. **Snapshot:** `{ "frequency_hz": float, "magnitude": float }`. | `src/heart/utilities/signal.py`. | Validate with sine sweep fixtures ensuring tracked bin matches ground truth.
| Entropy (Sample/Permutation) | Evaluates randomness/complexity for biosignals and control loops. | Sample entropy helper, permutation encoding. | **State:** stores entropy value and embedding dimension metadata. **Cadence:** 1 s windows. **Snapshot:** `{ "sample_entropy": float, "permutation_entropy": float }`. | `src/heart/utilities/statistics.py`. | Validate against known chaotic vs. periodic sequences.

## Hyper-Niche but Common Metrics (5)

| Metric | Purpose & Domain Relevance | Prerequisites | Scaffold Integration | Cross References | Validation & Data Requirements |
| --- | --- | --- | --- | --- | --- |
| Allan Variance | Quantifies sensor stability over averaging time for IMUs and clocks. | Overlapping Allan variance helper, logarithmic binning. | **State:** stores tau bins and variance values. **Cadence:** asynchronous batches triggered hourly or on demand. **Snapshot:** `{ "tau_s": list[float], "allan_var": list[float] }`. | `src/heart/peripheral/motion/imu.py`, `src/heart/utilities/stability.py`. | Use long-duration IMU captures; compare to reference Allan variance curves.
| Hurst Exponent | Indicates persistence vs. mean reversion for long-run processes. | Rescaled range calculations, fractional Brownian motion simulator. | **State:** retains Hurst estimate per stream. **Cadence:** 10 s rolling window with daily summarisation. **Snapshot:** `{ "hurst_exponent": float }`. | `src/heart/utilities/statistics.py::hurst_exponent`. | Validate using synthetic fBm with known exponents.
| Crest Factor | Monitors peak-to-RMS ratio to find impulsive events in vibration/audio. | RMS helper, peak detector. | **State:** stores peak and RMS pair. **Cadence:** 100 ms windows. **Snapshot:** `{ "crest_factor": float, "peak": float, "rms": float }`. | `src/heart/utilities/signal.py`. | Use vibration fixtures with controlled impulses to verify ratios.
| Kurtosis | Measures tail heaviness for shock detection across multiple domains. | Fourth-moment calculator, bias correction. | **State:** retains rolling kurtosis. **Cadence:** 1 s windows. **Snapshot:** `{ "kurtosis": float }`. | `src/heart/events/metrics.py::MomentMetric`. | Validate with Laplace vs. Gaussian synthetic distributions.
| Permutation Entropy | Captures ordinal pattern complexity to spot regime shifts. | Permutation vector encoder, factorial caching. | **State:** stores entropy value with embedding length metadata. **Cadence:** 2 s windows. **Snapshot:** `{ "permutation_entropy": float, "embedding": int }`. | `src/heart/utilities/statistics.py`. | Regression tests on logistic map vs. periodic sequences stored in fixtures.

# Visual Reference

| Category | Metric Families | Purpose & Domain Relevance | Prerequisites | Scaffold Mapping |
| --- | --- | --- | --- | --- |
| Runtime Performance | Event loop latency, queue depth histogram, render frame time percentiles, garbage collection pauses | Quantifies scheduler health for `src/heart/loop.py` and ensures renderers under `src/heart/renderer/` meet frame budgets | Access to monotonic timestamps, GC hooks, optional psutil for memory sampling | **State:** global loop counters and renderer tick IDs. **Cadence:** 100 ms loop snapshots with per-frame deltas. **Snapshot:** `{ "loop_latency_ms": float, "frame_p99_ms": float, "queue_depth_hist": dict }` |
| Peripheral Health | Accelerometer jerk RMS, gyroscope drift, heart-rate HRV, IR array confidence, UWB range residuals | Validates sensor accuracy and readiness; feeds diagnostics in `src/heart/peripheral/*` modules | Finite difference helpers, quaternion normalisation, Hilbert transform for envelope detection, per-device calibration tables | **State:** keyed by peripheral ID with rolling windows (5–20 s). **Cadence:** event-driven with min 50 ms stride. **Snapshot:** tuple mappings `{ peripheral_id: { "jerk_rms": float, ... } }` |
| Environment & Ambient | Temperature trend, humidity dew point deviation, CO₂ excursion duration, acoustic noise floor | Tracks external conditions influencing program behaviour and user comfort | Exponential moving averages, optional FFT for band-limited noise, integration with `src/heart/peripheral/environment/` sensors | **State:** keyed environment channels with both raw and smoothed values. **Cadence:** 5 s updates aggregated into 5 min windows. **Snapshot:** layered dict storing raw sample, EMA, excursion counters |
| Program Responsiveness | Playlist transition latency, scene load duration, effect trigger success rate, command queue backlog | Ensures higher-level programs under `src/heart/programs/` respond within expected SLA; critical for interactive scenes | Access to event bus hooks, timestamp correlation, idempotent counters, optional diff-based snapshot compressor | **State:** keyed by program and playlist handle. **Cadence:** on transition events plus 1 s heartbeat. **Snapshot:** includes timestamp arrays `{ program: { "transition_latency_ms": list, "command_backlog": int } }` |

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
