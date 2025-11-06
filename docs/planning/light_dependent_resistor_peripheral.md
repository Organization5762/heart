# Light-dependent resistor peripheral integration plan

## Abstract

The heart firmware currently samples discrete digital sensors but lacks an analog light-sensing capability that could enrich ambient-aware behaviors. This plan delivers a light-dependent resistor (LDR) module with calibrated lux estimations, focusing on firmware interfaces for the RP2040-based host and validation on the bench automation rig. The immediate driver is to unlock ambient-adaptive haptics before the next usability study. The work targets embedded engineers and the test automation team responsible for firmware releases and lab validation.

**Why now.** Current heuristics for ambient state rely on scheduled profiles, forcing manual overrides during demos. Adding a low-cost LDR peripheral gives continuous ambient feedback, enabling auto-dimming features slated for the Q3 field pilots while reusing the analog front-end already on the expansion board.

## Success criteria

| Target behaviour | Measurable signal | Validation owner |
| --- | --- | --- |
| Firmware publishes lux readings at 5 Hz with \<10% deviation from calibrated lux meter between 10–800 lux | Bench comparison against Extech SDL400 over 10-minute sweep | Firmware validation lead |
| Peripheral driver enters low-power state (\<150 µA draw) when host asserts sleep | Power rail current log captured via Otii Arc during scripted suspend/resume | Power systems engineer |
| Ambient-aware haptics pipeline consumes LDR readings without regression in latency budget (\<3 ms added) | Tracing output from `tracepoints/haptics_latency.json` regression suite | Haptics feature owner |

## Phase checklists

### Discovery

- [ ] Review existing `drivers/analog_frontend` API to confirm available ADC channels and reference voltage precision.
- [ ] Inventory passives on the expansion board to select resistor ladder values aligning with the RP2040 3.3 V ADC range.
- [ ] Capture existing power budget spreadsheet and annotate expected quiescent draw for the LDR voltage divider.
- [ ] Align with test automation on available light box fixtures and required scripting hooks.

### Implementation

- [ ] Add `drivers/ldr_sensor.py` driver exposing `init()`, `sample_lux()`, and `suspend()` consistent with `drivers/thermistor.py` patterns.
- [ ] Extend `drivers/analog_frontend` to allocate a dedicated ADC channel with interrupt-driven sampling at 200 Hz followed by firmware-side decimation to 5 Hz.
- [ ] Create calibration lookup table based on three-point lux measurements (10, 300, 800 lux) and store coefficients under `resources/calibration/ldr.json`.
- [ ] Integrate readings into the `src/ambient/pipeline.py` message bus with debounce filters aligned to the 5 Hz target.
- [ ] Update configuration schema (`src/config/schema.toml`) to allow enabling/disabling the LDR peripheral and tuning debounce constants.

### Validation

- [ ] Script bench run in `scripts/run_lux_sweep.py` to coordinate the Extech meter, programmable light source, and firmware logging endpoint.
- [ ] Extend `tests/integration/test_ambient_pipeline.py` with fixtures mocking calibrated lux inputs and asserting latency budgets.
- [ ] Execute power draw measurements via Otii and attach plot to validation report in `docs/reports/ldr_power.md`.
- [ ] Conduct cross-team review covering firmware, test automation, and product to sign off on success criteria.

## Narrative walkthrough

The discovery phase grounds the effort in current hardware constraints. Reviewing the analog front-end clarifies available ADC resolution and tolerance so the driver can normalize raw counts accurately. By inventorying passives and budgeting quiescent draw early, we avoid rework if the ladder conflicts with existing power envelopes. Coordinating with test automation ensures light box fixtures support scripted sweeps, reducing friction during validation.

Implementation focuses on modularity and reuse. The new driver mirrors established patterns, making it approachable for firmware reviewers. Assigning a dedicated ADC channel and decimating from a higher sampling rate keeps noise manageable while maintaining low CPU overhead. Calibration coefficients live alongside other resources to support future factory recalibration. The ambient pipeline integration ensures consumers receive filtered lux events without destabilizing existing subscribers. Configuration toggles provide a safe rollout path for field tests.

Validation emphasizes quantifiable evidence. The scripted bench run gives repeatable lux comparisons, while integration tests guard against latency regressions in the ambient pipeline. Power profiling with Otii verifies low-power behaviour, and the final review aligns stakeholders on release readiness.

## Visual reference

```
Ambient Light Flow
+--------------+     ADC samples     +------------------+    Lux events    +-------------------+
| LDR Sensor   | ----(voltage)----> | Analog Frontend  | --filtered----> | Ambient Pipeline  |
| (voltage div)|                    | (200 Hz ISR)      |  (5 Hz)         | (haptics trigger) |
+--------------+                    +------------------+                  +-------------------+
        |                                    |                                   |
        | suspend()                          | DMA gate                          | debounce
        v                                    v                                   v
   Low power mode                    Power manager                         Haptics scheduler
```

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| ADC reference drift skews lux conversion | Medium | High | Implement on-boot calibration routine comparing to stored coefficients and flag deviation | Continuous integration test comparing simulated counts to calibration curve |
| LDR voltage divider draws excessive idle current | Low | Medium | Select >100 kΩ resistors and gate supply via MOSFET tied to suspend control | Power budget spreadsheet exceeds allocated 150 µA |
| Ambient pipeline saturates during rapid light changes | Medium | Medium | Apply exponential moving average with configurable alpha and add backpressure metrics | Trace logs show >3 ms latency increase |
| Bench light box cannot cover lux range | Low | High | Coordinate with lab to retrofit ND filter stack or borrow alternate fixture | Discovery review notes insufficient lux coverage |

**Mitigation checklist**

- [ ] Prototype calibration routine on dev board and log coefficient drift across temperature sweep.
- [ ] Measure voltage divider current with and without MOSFET gating; adjust resistor values if margin \<20%.
- [ ] Instrument pipeline with latency counters and alert on Slack if thresholds exceed 3 ms.
- [ ] Secure backup light source booking before validation week and document contingency steps.

## Outcome snapshot

Once complete, the firmware exposes stable lux telemetry at 5 Hz with verified calibration accuracy. The ambient haptics pipeline can react to environmental changes without manual overrides, while the power manager enforces sub-150 µA draw in suspend. Validation artifacts—including calibration tables, power plots, and latency traces—live alongside documentation, enabling future requalification or factory recalibration. This unlocks data-driven iteration on ambient-aware features for the Q3 field pilot and future multi-sensor expansions.

## Author quality checklist

- [x] Opening abstract captures objective, context, and stakeholders.
- [x] Success criteria table lists measurable signals and owners.
- [x] Every phase contains actionable checklists.
- [x] Narrative walkthrough connects phases and sequencing.
- [x] Diagram clarifies data flow and control points.
- [x] Risk analysis table and mitigation checklist included.
- [x] Outcome snapshot details observable post-launch state.
- [x] Tone remains technical and evidence-oriented.
- [x] References to related artifacts embedded where helpful.
- [x] Word count lands between 800 and 1200 words.
