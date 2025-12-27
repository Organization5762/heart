# High-Bandwidth Camera Ingest Plan

## Problem Statement

Our runtime can ingest low-bandwidth sensor streams, but it lacks a deterministic path for high-frame-rate camera feeds. Without a DMA-backed capture path, frames would saturate the existing I²C and USB serial links, starve `src/heart/loop.py`, and keep navigation programs from responding to other peripherals.

## Materials

- Raspberry Pi 4 Model B running the Heart peripheral runtime.
- [PiCowbell Camera Breakout](https://www.adafruit.com/product/5946) connected over CSI-2 via the PiCowbell interface.
- [MLX90640 Thermal Camera](https://www.adafruit.com/product/4469) for comparative thermal-frame ingest over I²C.
- Existing Python peripheral framework under `src/heart/peripheral`, `src/heart/programs`, and `drivers`.
- USB 3.0 storage for logging raw and compressed frame captures.
- Access to the telemetry stack at `src/heart/utilities/telemetry.py` and the event pipeline under `src/heart/events`.

## Opening Abstract

We will extend the Heart runtime to capture, buffer, and distribute 60 FPS RGB camera streams without starving other peripherals. The plan establishes a CSI-2 DMA driver, double-buffered frame management, and queue-based delivery to downstream programs. A matching telemetry layer, validation suite, and operator documentation ensure the camera pipeline remains observable and tunable alongside existing Python-based peripherals.

## Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Sustained 60 FPS RGB capture without dropped DMA interrupts | `tests/peripheral/test_camera_stream.py::test_dma_backpressure` completes under 1.2x realtime | Peripheral firmware team |
| Event loop latency stays under 8 ms while streaming | Tracing in `src/heart/loop.py` shows \<8 ms between ticks during soak tests | Runtime team |
| Thermal camera coexistence path maintains 10 Hz updates | Integration test logs from `drivers/thermal_camera` show ≤5% frame loss | Sensor integration team |
| Telemetry dashboard exposes frame timings and buffer saturation | Metrics appear in the Grafana dashboard backed by `src/heart/utilities/telemetry.py` | Observability team |

## Task Breakdown Checklists

### Discovery

- [ ] Profile current bus usage in `drivers/sensor_bus` and `src/heart/environment.py` to quantify throughput headroom.
- [ ] Select CSI-2 capture mode for PiCowbell and document MLX90640 fallback parameters in `docs/hardware/inputs.md`.
- [ ] Draft a bandwidth budget covering frame size, rate, and compression at `docs/planning/camera_ingest_budget.xlsx`.

### Implementation

- [ ] Scaffold `drivers/camera/driver.py` with DMA setup, IRQ handlers, and teardown mirroring `drivers/rotary_encoder` patterns.
- [ ] Expose a `CameraFrameBuffer` under `src/heart/peripheral/camera/buffer.py` that manages double-buffered DMA regions and backpressure APIs.
- [ ] Extend `src/heart/firmware_io/__init__.py` to negotiate frame formats, crop regions, and trigger rate with the capture hardware.
- [ ] Wire `src/heart/loop.py` to poll the camera buffer via non-blocking calls and enqueue frames on `src/heart/events/queue.py`.
- [ ] Introduce `src/heart/programs/camera.py` with a `CameraIngestProgram` that publishes navigation-ready frame references.
- [ ] Implement frame-drop and downsample controls in `src/heart/peripheral/__init__.py` for overloaded consumers.

### Validation

- [ ] Emit DMA timing, queue depth, and frame integrity metrics using `src/heart/utilities/telemetry.py`.
- [ ] Build synthetic load tests in `tests/peripheral/test_camera_stream.py` that stress 60 FPS ingest alongside existing peripherals.
- [ ] Add soak tests invoking both PiCowbell and MLX90640 paths to validate coexistence and thermal stability.
- [ ] Update `docs/planning/camera_ingest_pipeline.md` with tuning steps, troubleshooting, and expected telemetry signatures.

## Narrative Walkthrough

Discovery quantifies how much CSI-2 bandwidth the PiCowbell path can consume before impacting USB and I²C peripherals. Profiling in `drivers/sensor_bus` and `src/heart/environment.py` gives concrete throughput headroom numbers. We capture this data and a frame budget so the DMA configuration has explicit limits. The MLX90640 path remains a secondary ingest option that validates our ability to downsample and multiplex lower-bandwidth thermal data.

Implementation starts by mirroring proven driver scaffolding. `drivers/camera/driver.py` sets up the CSI-2 interface, configures DMA descriptors, and delivers interrupts to the runtime. `CameraFrameBuffer` exposes a clean API for non-blocking frame swaps, while `src/heart/firmware_io` negotiates parameters with the hardware. Integrating with `src/heart/loop.py` ensures frame transfer occurs without blocking other event sources, and `CameraIngestProgram` maps raw buffers to downstream consumers. Finally, backpressure controls allow us to drop or downsample frames when programs fall behind, keeping the runtime responsive.

Validation layers observability on top of the capture stack. Telemetry emitted from the driver and buffer layers surfaces frame timing, DMA overruns, and queue saturation. Synthetic tests in `tests/peripheral/test_camera_stream.py` run high frame rates while verifying that event loop latency remains in spec. Thermal camera coexistence tests confirm the pipeline handles mixed bandwidth workloads. Documentation updates teach operators how to interpret telemetry, tune frame rates, and troubleshoot hardware or firmware faults.

## Visual Reference

| Stage | Module | Interface | Notes |
| --- | --- | --- | --- |
| Capture | `drivers/camera/driver.py` | CSI-2 lanes → DMA engine | Configures double-buffered descriptors and IRQ routing. |
| Buffering | `src/heart/peripheral/camera/buffer.py` | Shared memory → Python bindings | Provides `acquire_frame()` / `release_frame()` APIs with latency counters. |
| Coordination | `src/heart/firmware_io/__init__.py` | Control plane over I²C/USB | Negotiates format, triggers, and runtime parameters. |
| Scheduling | `src/heart/loop.py` + `src/heart/events/queue.py` | Async queue | Moves frames into queue without blocking tick loop. |
| Consumption | `src/heart/programs/camera.py` | Program registry | Publishes events for navigation, display, or ML inference. |
| Observability | `src/heart/utilities/telemetry.py` | Metrics sink | Emits timing, saturation, and error counters for dashboards. |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early warning signal |
| --- | --- | --- | --- | --- |
| DMA contention with existing USB drivers | Medium | High | Reserve dedicated DMA channels and prioritize interrupts for camera driver. | Kernel logs showing DMA allocation failures or IRQ latency spikes. |
| Event loop starvation under burst traffic | Medium | High | Enforce non-blocking buffer APIs and apply queue backpressure thresholds. | Telemetry indicates loop ticks exceeding 8 ms or queue depth spike alerts. |
| Thermal drift on MLX90640 during long runs | Low | Medium | Insert cool-down cadence and monitor sensor temperature via auxiliary reads. | Gradual increase in per-frame offset reported by thermal driver diagnostics. |
| Frame corruption due to CSI signal integrity | Low | High | Use shielded ribbon cables, validate signal quality with test patterns, and enable ECC if available. | CRC error counters rising in driver telemetry. |

### Mitigation Checklist

- [ ] Reserve CSI-specific DMA channels in device tree overlays and document them in `docs/hardware/rpi_device_tree.md`.
- [ ] Configure watchdog telemetry alerts in Grafana for event loop latency and queue depth.
- [ ] Script MLX90640 drift checks in `tests/peripheral/test_thermal_camera.py`.
- [ ] Run signal integrity sweeps after cabling changes and log outcomes in `docs/hardware/camera_cabling.md`.

## Outcome Snapshot

Once complete, the Heart runtime streams 60 FPS RGB frames from the PiCowbell camera while simultaneously handling MLX90640 thermal updates and existing peripherals. Developers can tune frame formats through `src/heart/firmware_io`, monitor real-time metrics in Grafana, and rely on automated tests to guard against regressions. The pipeline delivers frames to navigation and rendering programs without violating event loop latency budgets, and the documentation provides clear steps for operations, troubleshooting, and future scaling.
