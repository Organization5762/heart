# Core Renderer Performance Initiative

## Problem Statement

The renderer stack in `src/heart/display/renderers/` and its orchestration in `src/heart/environment.py` spend excessive CPU cycles assembling intermediate `pygame.Surface` objects, replaying identical scene setup logic, and serialising animation frames individually. These patterns slow frame production on limited hardware and make it hard to capture deterministic playback traces. We need a coordinated plan to quantify the bottlenecks, redesign the rendering loop, and introduce tooling for reproducible performance analysis without regressing image quality or API ergonomics.

## Materials

- Development host with Python 3.11, `pygame`, profiling dependencies already expressed in `pyproject.toml`, and GPU-less execution parity with production Raspberry Pi builds.
- Representative animation assets: spritesheets under `src/heart/display/renderers/spritesheet*`, fractal workloads in `src/heart/display/renderers/mandelbrot/`, and text-heavy layouts from `src/heart/display/renderers/text.py`.
- Access to profiling and tracing utilities: `cProfile`, `py-spy`, `line_profiler`, and the repository's logging configuration in `src/heart/logging.py`.
- Existing automated test harness (`make test`) plus manual access to the physical LED matrix for end-to-end validation when possible.
- Storage for trace artefacts (GIF sequences, frame timing CSVs) organised under `docs/research/renderer_performance/`.

## Opening Abstract

We will iteratively improve the renderer pipeline by first capturing quantitative baselines, then optimising frame assembly and data movement, and finally shipping developer tooling to replay and analyse scenes. Key deliverables include: (1) a pre-tracing subsystem that records renderer outputs into compact frame buffers for GIF emission, (2) a high-performance pixel writer that minimises intermediate surfaces, and (3) instrumentation hooks that feed runtime metrics into automated regression checks. Success requires careful integration with the modular renderer API so existing modes continue to function while gaining observable performance headroom.

## Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| 25% reduction in mean frame render time for `RandomPixel` and `MandelbrotMode` scenes | `pytest tests/performance/test_renderer_timings.py` reports \<= 12 ms per frame on reference hardware | Core rendering engineer |
| Deterministic pre-tracing export covering 120 seconds of animation | `scripts/trace_renderers.py` produces GIF + JSON index matching checksum references | Tooling engineer |
| Runtime metrics exposed via `Environment.process_renderer` logs | Structured logs show frame duration, queue depth, and GPU flag with \<1% log drop | Observability engineer |

## Task Breakdown Checklists

### Phase 1 — Discovery and Baseline

- [ ] Instrument `Environment.process_renderer` with lightweight timing scopes writing to the existing logger for offline analysis.
- [ ] Add `tests/performance/test_renderer_timings.py` with fixtures that render deterministic scenes using seeded RNG to establish baseline timings.
- [ ] Capture flame graphs for `RandomPixel`, `SpritesheetLoop`, and `MandelbrotMode` via `py-spy record`, storing artefacts in `docs/research/renderer_performance/baseline/`.
- [ ] Document cache hit rates for renderer warm-up assets by tracing `BaseRenderer.initialize` calls.

### Phase 2 — Rendering Pipeline Improvements

- [ ] Design a `FrameAccumulator` helper under `src/heart/display/renderers/internal/` that lets renderers enqueue drawing commands without immediate surface allocation.
- [ ] Refactor `Environment._render_fn` to support batching renderers sharing identical device display modes and pixel formats.
- [ ] Introduce an optional pixel buffer reuse path for `SpritesheetLoop` and `RandomPixel` renderers, eliminating per-frame surface instantiation.
- [ ] Add unit tests validating that the new batch path produces identical pixel arrays to the legacy path for representative scenes.

### Phase 3 — Pre-Tracing and Tooling

- [ ] Implement `scripts/trace_renderers.py` to run a scene for N frames, record per-frame metadata, and emit GIF + JSON artefacts.
- [ ] Extend `BaseRenderer` with hooks to share deterministic seeds and state snapshots for trace replay.
- [ ] Build regression checks in `tests/performance/test_trace_replay.py` ensuring traced GIFs match pixel hashes from live rendering.
- [ ] Add documentation in `docs/research/renderer_performance/README.md` describing trace workflows and retention policy.

### Phase 4 — Validation and Rollout

- [ ] Re-run performance benchmarks and compare against discovery baselines, committing artefacts showing at least 25% improvement.
- [ ] Conduct soak tests on hardware using `Tiltfile` flows to validate long-running stability with the new pipeline.
- [ ] Update operational runbooks (`docs/operations/renderer.md`) with instructions for enabling tracing and reading metrics.
- [ ] Present findings in an engineering review, capturing open issues and potential follow-on tasks.

## Narrative Walkthrough

Discovery grounds the initiative by placing hard numbers on render loop costs. Timing instrumentation added to `Environment.process_renderer` and `BaseRenderer._internal_process` exposes hotspots such as repeated surface creation and Python-level per-pixel loops. The dedicated performance tests and flame graphs allow us to compare subsequent optimisations objectively. Baseline artefacts stored under `docs/research/renderer_performance/` become the canonical reference for the rest of the project.

Armed with empirical data, Phase 2 tackles the core inefficiencies. The new `FrameAccumulator` provides a staging layer so renderers can emit blit operations and palette manipulations without allocating intermediate buffers. By batching renderers sharing display characteristics inside `_render_fn`, we decrease context switches and redundant conversions. Pixel buffer reuse for sprites and procedural renderers cuts down on GC pressure and Python overhead. Tests guarantee these changes preserve visual fidelity.

Phase 3 introduces tooling to pre-trace scenes. `scripts/trace_renderers.py` leverages the accumulator to run renderers offscreen, capturing frames and metadata into a reproducible package. Extending `BaseRenderer` with deterministic seeds ensures that traces can be replayed across environments. Regression tests validate that traced output matches live renders via hash comparisons, protecting against drift.

Finally, Phase 4 focuses on validation and rollout. Benchmarks rerun on the same workloads confirm performance targets. Soak tests through the existing `Tiltfile` pipeline catch resource leaks or scheduler contention. Documentation updates and an engineering review close the loop, equipping operations with the knowledge to deploy and monitor the improved renderer.

## Visual Reference

| Pipeline Stage | Module(s) | Description |
| --- | --- | --- |
| Scene Selection | `src/heart/environment.py` (`Environment._render_fn`) | Chooses active renderers, now batching by display mode and reusing pixel buffers. |
| Command Accumulation | `src/heart/display/renderers/internal/frame_accumulator.py` | Collects draw calls and metadata without allocating surfaces until flush time. |
| Frame Synthesis | `src/heart/display/renderers/__init__.py` (`BaseRenderer._internal_process`) | Applies draw commands onto shared buffers, emitting final pixel arrays. |
| Trace Export | `scripts/trace_renderers.py` | Streams accumulated frames to GIF + JSON artefacts for deterministic playback. |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning |
| --- | --- | --- | --- | --- |
| New accumulator introduces race conditions under multi-threaded rendering | Medium | High | Gate shared buffer access with explicit locks in `Environment._render_fn`; add stress tests with concurrent executors | Unit tests intermittently fail due to mismatched pixel hashes |
| Pre-tracing inflates storage footprint | Medium | Medium | Compress traces, enforce retention policy documented in `docs/research/renderer_performance/README.md` | Storage monitoring alerts or git LFS quota nearing limit |
| Pixel buffer reuse causes compatibility issues with OpenGL renderers | Low | High | Keep legacy path as fallback, guarded by feature flag in configuration | Logs show fallback activation rate exceeding 5% |
| Profiling overhead skews benchmark results | Medium | Low | Run with and without profilers; record instrumentation overhead for context | Baseline timings vary more than 10% between runs |

### Mitigation Checklist

- [ ] Add concurrency tests in `tests/performance/test_renderer_timings.py` covering multi-threaded accumulators.
- [ ] Configure automated trace pruning script under `scripts/cleanup_traces.py` with documentation.
- [ ] Introduce configuration flag `RendererPerformanceConfig` in `src/heart/utilities/env.py` to toggle buffer reuse.
- [ ] Validate profiling impact by recording control runs without instrumentation and documenting results.

## Outcome Snapshot

Once complete, the renderer stack produces frames at least 25% faster on the reference hardware, with deterministic trace exports available for any scene. Developers can reproduce performance measurements locally using automated tests and stored baseline artefacts. Operations teams can enable tracing, monitor frame durations, and manage artefact retention using documented procedures, while renderers maintain backwards compatibility through feature flags and regression coverage.
