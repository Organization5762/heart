# IR Sensor Array Positioning Notes

## Problem statement

The firmware stack needs a reproducible method to convert timestamped edges from
an infrared (IR) sensor array into centimetre-scale pose estimates. Legacy IR
decoders in `drivers/` capture level transitions but discard precise arrival
times, which prevents multilateration. We require a data model that preserves
microsecond timing, a solver that tolerates sensor skew, and supporting tooling
for calibration.

## Materials and context

- Four-channel IR sensor breadboard driven over USB/UART for prototyping.
- Host workstation capable of running the Python event loop and PyTest suite.
- Existing Heart runtime modules (`heart.peripheral.core`, event bus, logging).
- Synthetic capture fixtures stored as JSON for calibration experiments.

## Timing capture audit

The existing sensor bus code paths in `drivers/` timestamp rising edges with
millisecond precision before forwarding payloads to the host. This is
insufficient for triangulation: 1 ms of uncertainty at the speed of light
produces ~300 km of spatial error. We therefore implemented
`IRArrayDMAQueue` in `src/heart/peripheral/ir_sensor_array.py` to simulate the
embedded double-buffered DMA queue. The queue stores raw `IRSample` objects with
microsecond resolution, computes a lightweight CRC across each buffer, and emits
`IRDMAPacket` instances that the host peripheral validates prior to decoding.

## Geometry model and solver

`MultilaterationSolver` consumes a fixed array of sensor positions and solves
for the burst origin via a constrained least-squares fit. The implementation
wraps `scipy.optimize.least_squares` so the solver can explore the joint space
of pose and emission time while respecting tight convergence thresholds. The
radial layout helper staggers sensors vertically (±15% of the radius) to break
planar degeneracy. The solver returns both a pose estimate and a confidence
score derived from the residual root mean square error (RMSE). Unit tests in
`tests/peripheral/test_ir_sensor_array.py::test_multilateration_solver_converges_on_known_point`
exercise the solver with synthetic geometry and confirm convergence to a known
point within a millimetre.【F:src/heart/peripheral/ir_sensor_array.py†L118-L207】【F:tests/peripheral/test_ir_sensor_array.py†L28-L52】

## Solver performance and configuration

The solver now evaluates residuals using vectorized NumPy operations and
supplies an analytical Jacobian for the least-squares optimizer. This reduces
per-iteration Python overhead and provides direct control over the gradient
estimate. The solver method (`trf` by default) and Jacobian usage are
configuration parameters on both `MultilaterationSolver` and `IRSensorArray`,
so deployments can tune convergence behaviour alongside frame processing
without modifying the algorithm itself.【F:src/heart/peripheral/ir_sensor_array.py†L118-L268】

## Frame assembly and decoding

`FrameAssembler` groups samples by `frame_id` until every sensor contributes.
When a frame is complete, the peripheral assembles an `IRFrame` that exposes
both calibrated arrival times and a coarse payload bitstream. The current
decoder treats pulses longer than 1 ms as logical ones; shorter pulses map to
zeros. This heuristic matches the directional remote fixture described in the
planning document and can be tuned once actual modulation measurements arrive.

`IRSensorArray` feeds the solver, applies optional per-channel calibration
offsets, and emits pose events through the runtime `EventBus`. Tests in
`tests/peripheral/test_ir_sensor_array.py::test_sensor_array_emits_frame_event`
demonstrate that the peripheral produces a frame event with centimetre accuracy
and expected payload bits after applying synthetic calibration offsets.【F:src/heart/peripheral/ir_sensor_array.py†L191-L264】【F:tests/peripheral/test_ir_sensor_array.py†L54-L90】

## Calibration workflow

The CLI defined in `scripts/ir_calibrate.py` ingests JSON captures generated
from lab sweeps. Each record describes the emitting pose, sensor index, and the
observed timestamp. The tool groups captures by `frame_id`, compares observed
arrival times to the theoretical propagation delay given a supplied sensor
layout, and writes the per-sensor median offset and aggregate metrics (RMSE,
frames used, maximum skew). Operators can optionally push the resulting payload
to a telemetry endpoint directly from the CLI to prime runtime dashboards.【F:scripts/ir_calibrate.py†L1-L144】

## Validation snapshot

- `IRArrayDMAQueue` toggles buffers correctly and preserves sample ordering.
- Multilateration unit test reproduces emitter coordinates within 1 mm.
- Peripheral integration test verifies confidence scoring above 0.95 with
  residuals below `1e-10` seconds.
- CLI computes offsets from synthetic fixtures and enforces input validation to
  avoid silent miscalibrations.

## Follow-up

- Integrate live capture tooling on the embedded board to populate
  `IRDMAPacket` directly from DMA hardware.
- Replace the pulse-width heuristic with protocol-specific decoding once the
  remote modulation scheme is finalised.
- Extend the calibration CLI to stream results to the telemetry store outlined
  in the planning document.
