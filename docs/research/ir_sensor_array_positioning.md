# IR Sensor Array Positioning Research Note

## Context

This note captures the technical rationale for adding an IR sensor array peripheral that decodes remote-control bit streams while estimating emitter pose. It complements the implementation plan documented in `docs/planning/ir_sensor_array_peripheral.md` by diving into timing tolerances, sensor geometry, and signal processing trade-offs.

## Timing and sampling requirements

- Target end-to-end latency is \<50 ms from photon detection to multilateration output, matching the success criteria in the plan.
- Each sensor channel must support microsecond-scale timestamping. With sensors spaced 15–20 cm apart, a 10 cm path difference corresponds to ~333 ns in air; sub-microsecond precision with oversampling and interpolation is required to differentiate arrival times reliably.
- Use a phase-locked loop (PLL) disciplined clock distributed to all capture channels. Breadboard experiments should log phase noise and drift across temperature ranges before committing to PCB layout.

## Sensor package evaluation

| Package | FOV | Responsivity | Rise time | Notes |
| --- | --- | --- | --- | --- |
| TSOP-like demodulators | 90° | High | 400 µs | Integrated AGC may mask fine timing; suitable for decoding but weak for triangulation |
| PIN photodiodes + transimpedance | 60° (with lens) | Medium | \<10 µs | Requires custom amplification but preserves edge timing |
| Multi-element IR receivers | 120° | Medium | 50 µs | Wider coverage but higher crosstalk risk; useful for hybrid arrays |

**Recommendation:** Combine narrow-FOV PIN photodiodes for timing accuracy with secondary demodulation channels to retain compatibility with legacy remotes.

## Geometry and solver design

- Arrange four sensors in a non-coplanar radial geometry to maximize baseline diversity. A tetrahedral layout yields better vertical resolution than a flat plane.
- Implement a multilateration solver that ingests time-of-arrival (ToA) differences plus binary hit flags for robustness when signals clip.
- Confidence scoring should weight solutions by the variance of measured ToA residuals and ambient light noise captured during calibration sweeps.

## Directional remote encoding

- Prototype a remote with three IR LEDs spaced at 120° and mounted on a small dome to project distinct beams.
- Assign unique preambles (P1, P2, P3) per emitter and stagger bursts with 3 ms guard intervals. This approach aligns with the frame sequencing table in the plan and mitigates reflective interference.
- Encode pose hints within payload bits when possible (e.g., beam ID + sync pulse) so the solver can reject ambiguous detections.

## Calibration and observability

- Calibration CLI should capture static sweeps at multiple distances (1–3 m) and solve for sensor offsets, temperature coefficients, and photodiode gain factors.
- Store calibration artifacts in the telemetry backend so soak tests can correlate drift with environment data.
- Dashboard visualizations must expose per-sensor status, timing residuals, and confidence metrics to aid troubleshooting.

## Open research questions

1. What modulation frequencies minimize ambient sunlight interference while staying within component tolerances?
1. How does reflective clutter (glass, metal) impact ToA measurements, and can adaptive filtering compensate without increasing latency?
1. Can we multiplex multiple directional remotes without sacrificing ToA resolution? Potential solutions include orthogonal frequency codes or time-sliced frames beyond the current five-segment schedule.

## References

- Implementation plan: `docs/planning/ir_sensor_array_peripheral.md`
- DMA and timestamping prototypes: to be stored in `src/hw/ir_array.rs` and accompanying test fixtures once development begins.
