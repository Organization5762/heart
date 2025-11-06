# Benchmarking Instrumentation Plan

The benchmarking work should focus on instrumenting the existing game loop (`src/heart/environment.py::GameLoop`) and rendering pipelines (`src/heart/display/...`) while exposing reproducible tooling to profile runs end-to-end. **A core goal for every task below is to align the nomenclature and structure with OpenTelemetry (OTel) concepts**—treating measurements as traces, spans, metrics, and attributes—so the resulting data can plug into standard OTel tooling with minimal translation.

## 1. Capture raw input latency across the peripheral stack

- Hook into the pygame event ingestion path in `GameLoop._handle_events` and the downstream event bus handlers in `src/heart/peripheral/core/` to timestamp each stage (hardware poll → pygame event → internal event bus → application handler).
- Surface a tracing helper (e.g., `src/heart/utilities/metrics.py`) that behaves like an OTel tracer: create spans per event, attach span events and attributes, and emit structured telemetry frames that can be correlated later.

### Task Stub — Instrument peripheral and event bus latency

1. Add a lightweight `LatencyTracer` helper under `src/heart/utilities/metrics.py` that mirrors the OpenTelemetry tracer API with `start_span()`, `record_event(stage_name)`, and `end_span()` helpers backed by a dataclass.
1. In `src/heart/environment.py::GameLoop._handle_events`, create a trace per pygame event (seeded with `time.perf_counter()`), recording span events for queue dequeue, event bus emission, and app controller handling (`AppController.process_events`).
1. For physical peripherals (`src/heart/peripheral/core/manager.py`, `src/heart/peripheral/core/event_bus.py`), extend the manager to optionally call `span.add_event("peripheral", {"handler": <name>})` when a handler consumes the event.
1. Expose the spans via an in-memory ring buffer and a debug CLI endpoint (e.g., `heart.loop:bench-input`) that dumps OTLP-compatible JSON for offline analysis or export to OTel backends.

## 2. Measure rendering FPS and per-renderer costs

- Instrument `GameLoop._render_surface_iterative`, `GameLoop._render_surfaces_binary`, and `GameLoop.__finalize_rendering` to track render durations per renderer (`BaseRenderer._internal_process`) and final blit/push to the physical device (`Device.set_image` implementations in `src/heart/device/`). Treat each renderer invocation as a child span of the frame span, tagging spans with renderer names and surface metadata attributes.

### Task Stub — Track rendering frame timings

1. Augment `src/heart/environment.py` to wrap each renderer call with `perf_counter()` timings, aggregating per-renderer averages and percentiles, and publishing them as OTel metrics (e.g., `FrameRenderDuration` histogram) alongside span timing data.
1. For the binary/iterative renderer paths, capture total render time, GPU/upload time (`pygame.display.flip`), and device push time (`Device.set_image`), storing them as span attributes and histogram datapoints in the metrics helper.
1. Update device drivers (`src/heart/device/rgb_display.py`, `src/heart/device/local.py`) to optionally emit timing callbacks back to the metrics subsystem, following OTel semantic conventions for device metrics where possible.
1. Provide a periodic HUD/overlay renderer (`src/heart/display/renderers`) that can display current FPS, render cost per renderer, and upload latency when benchmarking mode is enabled, pulling values from the shared OTel metric instruments.

## 3. Track core loop processing FPS and scheduling jitter

- Record loop iteration durations around `_handle_events`, `_preprocess_setup`, renderer selection, and `clock.tick(self.max_fps)` to distinguish CPU-bound vs. IO-bound stalls, representing the entire frame as an OTel span with nested spans for each stage.

### Task Stub — Measure core loop throughput

1. Encapsulate the main loop body in `GameLoop.start` with timing checkpoints (`loop_start`, `events_done`, `render_done`, `frame_presented`) represented as child spans within the frame span.
1. Compute instantaneous FPS (1 / loop duration) and maintain histograms/rolling averages stored as OTel metrics (e.g., `GameLoopFrameRate`) in the metrics helper.
1. Emit a structured record (e.g., JSON lines or OTLP export) at a configurable interval (`--benchmark-log /tmp/loop_metrics.jsonl`) for offline visualization and compatibility with OTel collectors.
1. Add CLI switches on `heart.loop:run` to enable/disable benchmarking overlays and logging sinks without impacting normal gameplay, including toggles for trace sampling rates consistent with OTel configuration terminology.

## 4. Generate flame graphs and detailed profiles

- Introduce scripts in `scripts/benchmark/` to run the loop under profilers like `py-spy`, `scalene`, or `yappi`, capturing wall-clock vs. CPU time and integrating with the OTel traces and metrics emitted by the instrumentation logs.

### Task Stub — Automate flamegraph profiling

1. Create `scripts/benchmark/run_pyspy.sh` that launches `python -m py_spy` against `heart.loop:run --benchmark-mode` and saves `pyspy.flamegraph.svg`, annotating the resulting trace metadata with the OTel trace ID for correlation.
1. Add a Python entry point (`scripts/benchmark/profile_loop.py`) that can toggle between profilers (cProfile + `snakeviz`, `pyinstrument`) and align profiler timestamps with the OTel trace/metric export windows via shared start times.
1. Document the workflow in `docs/benchmarking.md`, including commands for capturing input-latency traces, renderer timing logs, and flame graphs, plus guidance on interpreting the overlays with OTel viewers (e.g., Jaeger, Tempo, Trace Viewer).
1. Optionally integrate with `make benchmark` to bundle log collection and flamegraph generation into a single reproducible command while emitting OTLP files for downstream collectors.

## 5. Correlate metrics and surface bottlenecks

- Provide tooling to merge the recorded traces (input, rendering, loop) into an interactive visualization similar to a flame graph, possibly using `speedscope` or a custom Plotly dashboard, starting from the OTel trace data.

### Task Stub — Visualize combined metrics

1. Write a post-processing script (`scripts/benchmark/aggregate_metrics.py`) that ingests JSONL or OTLP traces and outputs a Chrome trace (`.json`) compatible with `speedscope` for flamegraph-style analysis.
1. Map each instrumentation stage (input, event, renderer, device upload) to hierarchical spans and span events to highlight bottlenecks per frame while preserving OTel semantic attributes.
1. Bundle a convenience `make benchmark-report` target that runs aggregation and opens the generated visualization (or prints the path in headless environments), optionally exporting the data as an OTel trace for direct import into tools like Tempo or Jaeger.
1. Expand `docs/benchmarking.md` with instructions for reading the combined trace, correlating OTel trace/metric IDs, and diagnosing latency hot spots.

This plan keeps the benchmarking tooling self-contained, adds minimal overhead behind feature flags, and produces actionable visualizations to pinpoint latency and FPS regressions while speaking the same language as OpenTelemetry so we can lean on the broader ecosystem of tooling.
