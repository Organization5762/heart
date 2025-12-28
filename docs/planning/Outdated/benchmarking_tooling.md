# Benchmarking Instrumentation Plan

## Problem Statement

Instrument the Heart runtime to measure input latency, rendering performance, and loop throughput using OpenTelemetry-aligned primitives without perturbing gameplay.

## Materials

- Current runtime source (`src/heart/environment.py`, `src/heart/display`, `src/heart/peripheral`).
- Python profiling tools (`py-spy`, `scalene`, `cProfile`).
- Access to an OpenTelemetry collector or JSONL log sink for validation.
- Workstations capable of running the runtime under profiling load.

## Opening Abstract

We lack consistent visibility into input latency and frame pacing. The plan introduces instrumentation that models runtime behaviour as OTel traces, spans, and metrics so we can analyse regressions with standard tooling. By gating instrumentation behind flags and exporting both realtime overlays and offline artefacts, developers can profile locally, operators can validate deployments, and CI can capture regressions.

### Why Now

Upcoming feature work adds new peripherals and renderers, and installations demand predictable frame rates. Adding instrumentation ahead of those changes gives us baselines and integrates with existing observability stacks.

## Success Criteria

| Behaviour | Signal | Owner |
| --- | --- | --- |
| Input latency spans cover hardware poll through application handler | Trace export shows sequential events with timestamps per stage | Runtime engineer |
| Renderer timing metrics recorded per renderer and device push | Histogram `FrameRenderDuration` emitted when benchmarking mode enabled | Graphics lead |
| Benchmark workflow documented and reproducible | `make benchmark` generates logs, flamegraphs, and instructions without manual edits | Developer experience |

## Task Breakdown Checklists

### Discovery

- [ ] Review current event handling in `GameLoop._handle_events` and peripheral managers.
- [ ] Inventory renderer code paths (`_render_surface_iterative`, `_render_surfaces_binary`, device drivers).
- [ ] Evaluate existing profiling scripts and gaps versus OTel concepts.

### Implementation – Instrumentation

- [ ] Add a `LatencyTracer` helper under `src/heart/utilities/metrics.py` mirroring OTel span APIs.
- [ ] Wrap event handling, renderer invocation, and loop checkpoints with span creation and events.
- [ ] Emit histograms for frame duration, renderer cost, and device upload latency.
- [ ] Provide CLI toggles (`--benchmark-mode`, `--benchmark-log`) controlling sampling rates and sinks.

### Implementation – Tooling

- [ ] Create `scripts/benchmark/run_pyspy.sh` and `scripts/benchmark/profile_loop.py` for automated profiling runs.
- [ ] Build a HUD renderer displaying live FPS and latency when benchmarking is active.
- [ ] Write aggregation utilities (`scripts/benchmark/aggregate_metrics.py`) to convert traces into `speedscope`-compatible JSON.

### Validation

- [ ] Capture sample runs on macOS and Linux, verifying trace exports and metrics formatting.
- [ ] Run profiling scripts against simulated loads to confirm flamegraphs align with spans.
- [ ] Ensure instrumentation overhead remains below 5% when disabled.

## Narrative Walkthrough

Discovery establishes where to capture timings and how current modules communicate so spans align with real behaviour. Instrumentation then introduces reusable helpers, wraps critical sections, and publishes metrics without changing business logic. Tooling builds the surrounding scripts and overlays to consume the new signals. Validation exercises the full workflow across platforms, checking export compatibility and runtime overhead.

## Visual Reference

| Metric | Source Stage | Export Format |
| --- | --- | --- |
| Input latency | `GameLoop._handle_events`, peripheral managers | Span events + JSONL trace |
| Renderer duration | Renderer invocations, device uploads | Histogram + span attributes |
| Loop throughput | `GameLoop.start` checkpoints | OTel counter + trace |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning |
| --- | --- | --- | --- | --- |
| Instrumentation alters frame pacing | Medium | High | Guard with feature flags and benchmark overhead during validation | FPS drops >5% when benchmarking disabled |
| Trace volume overwhelms log sinks | Medium | Medium | Implement sampling controls and rolling buffers | Log exporter reports backpressure |
| Misaligned timestamps between tracers and profilers | Low | Medium | Synchronise start times and embed trace IDs in profiler output | Flamegraph annotations lack trace IDs |

### Mitigation Tasks

- [ ] Measure runtime overhead with instrumentation disabled and adjust sampling defaults.
- [ ] Add configuration to cap export size and rotate log files.
- [ ] Annotate profiler scripts with trace metadata for correlation.

## Outcome Snapshot

Developers can enable benchmarking mode to capture OTel-aligned traces, metrics, and flamegraphs. The resulting artefacts highlight input latency, renderer bottlenecks, and loop jitter, enabling regression detection across releases.
