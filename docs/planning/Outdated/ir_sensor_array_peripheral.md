# IR Sensor Array Peripheral & Directional Remote Plan

## Abstract

The Heart hardware stack needs an infrared (IR) sensor array peripheral capable of decoding remote-style bit streams while estimating the three-dimensional origin of those transmissions. The target operators are hardware R&D, embedded firmware, and UX engineers who depend on sub-10-centimetre positional accuracy to unlock gesture-like interactions. **Why now:** the robotics roadmap demands centimeter-level indoor localization without adding radio-frequency complexity, and IR triangulation offers the fastest route to cross-team value. This plan orchestrates hardware, firmware, and experience threads so the first release lands with verifiable positioning accuracy, manufacturable prototypes, and observability hooks.

## Success criteria

| Celebration moment | Signal check | Owner |
| --- | --- | --- |
| Sensor rig resolves IR remote position within ±10 cm at a 3 m range | Lab calibration logs report \<10 cm mean error across 30 azimuth/elevation pairs | Hardware R&D |
| Firmware streams decoded bit packets and per-sensor timestamps at 200 Hz | Telemetry dashboard plots synchronized bit frames and inter-sensor timing deltas | Embedded firmware |
| Arrayed remote broadcasts directional patterns recognized in under 50 ms | Hardware-in-the-loop (HIL) test suite passes directional burst scenarios with \<50 ms latency | Controls & QA |

## Phase breakdown

### Discovery

- [x] Map the existing IR decoding flow in `drivers/` and document timing resolution limits in `docs/research/ir_sensor_array_positioning.md`.
- [ ] Benchmark wide-angle versus narrow field-of-view IR sensor packages; capture a comparison table with responsivity, latency, and ambient rejection metrics.
- [ ] Prototype a four-sensor breadboard with synchronized capture, saving logic analyzer traces and timestamp alignment notes to the lab share.
- [ ] Draft a communications spec for the peripheral-to-MCU interface (SPI vs. I²C + DMA) and solicit asynchronous feedback via architecture review notes.
- [ ] Interview firmware and UX partners about directional interaction scenarios to align on success narratives and telemetry requirements.

### Build

- [ ] Design PCB v1 with radial IR sensor placement, precision clock distribution, and diagnostic headers; store KiCad sources alongside BOM revisions.
- [ ] Implement the embedded driver module `src/hw/ir_array.rs` that streams timestamped interrupts into a double-buffered DMA queue with CRC tagging.
- [x] Extend the signal processing pipeline with a multilateration solver, confidence scoring, and unit tests using synthetic pulse fixtures.
- [ ] Create an arrayed remote prototype with three IR LEDs at 120° offsets, each modulating distinct preamble sequences and payload slots.
- [x] Develop a calibration CLI (`scripts/ir_calibrate.py`) that records sweeps, solves for sensor offsets, and uploads results to the telemetry store.

### Rollout

- [ ] Integrate a telemetry panel into the developer dashboard visualizing 3D pose estimates, signal strengths, and per-sensor status.
- [ ] Author the operator playbook covering placement, calibration cadence, and troubleshooting flows for missed pulses.
- [ ] Run a 48-hour soak test in the staging lab, logging positional drift, packet-loss events, and temperature correlations to observability sinks.
- [ ] Prepare launch communications (demo video, metrics snapshot, FAQ) for customer success and solution engineering partners.
- [ ] Capture win stories from early adopters and funnel them into the next roadmap review alongside backlog adjustments.

## Narrative walkthrough

Discovery focuses on proving feasibility and bounding timing performance. Hardware researchers map the current IR decoder to understand interrupt latency and sampling jitter while cataloguing sensor package trade-offs. The breadboard prototype validates that we can latch interrupts in microsecond windows and align them across four sensors with a shared reference clock. In parallel, architecture discussions lock in a low-latency peripheral interface, and partner interviews define the directional interaction stories that downstream teams expect to demo.

Build advances on three intertwined threads. Hardware spins the first PCB with radial sensor placement that maximizes baseline lengths while preserving a compact footprint. Firmware teams implement the timestamped data plane and multilateration solver, leaning on synthetic pulse fixtures to validate geometry maths before hardware arrives. Experience engineers craft the directional remote so the positional solver receives a structured burst sequence that encodes spatial cues as well as payload bits. The calibration CLI unblocks lab technicians by automating sensor offset estimation and uploading coefficients to shared storage.

Rollout layers on observability and enablement. The telemetry panel provides live dashboards for engineering reviews and soak tests. Operator enablement materials equip onsite teams to install, calibrate, and troubleshoot with minimal assistance. The extended soak test validates thermal stability, positional drift, and packet resilience before customer-facing demos. Launch communications and win-story capture ensure commercial and product stakeholders understand the gains and funnel real-world feedback into the follow-on backlog.

## Visual references

```
            Arrayed Remote (3-beam IR emitter)
                   /       |       \
                  /        |        \
       Sensor A ----- Sensor B ----- Sensor C ----- Sensor D
           (Δt₁)         (Δt₂)         (Δt₃)         (Δt₄)
                  \        |        /
                   \       |       /
          Multilateration solver → 3D pose + confidence score
```

| Frame segment | Emitter | Purpose | Duration |
| --- | --- | --- | --- |
| 1 | Beam 1 | Preamble P1 + payload burst | 10 ms |
| 2 | — | Guard gap to avoid cross-talk | 3 ms |
| 3 | Beam 2 | Preamble P2 + payload burst | 10 ms |
| 4 | — | Guard gap | 3 ms |
| 5 | Beam 3 | Preamble P3 + sync pulse | 5 ms |

> **Tip:** Record guard-gap timing with ±0.5 ms tolerance; exceeding this window is the earliest indicator of PLL drift or firmware scheduling hiccups.

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| Sensor timing jitter exceeds multilateration tolerance | Medium | High | Add PLL-based clocking and oversample interrupts with hardware timestamping | Calibration residuals above 15 cm |
| Arrayed remote beams interfere in reflective rooms | Medium | Medium | Stagger modulation frequencies, widen guard gaps, and add error correction coding | Spike in checksum failures during soak tests |
| Firmware throughput saturates MCU DMA bandwidth | Low | High | Use double-buffered DMA, compress timestamp payloads, and enforce watchdog telemetry | Telemetry backlog or dropped frames |
| Calibration drift correlates with ambient temperature | Medium | Medium | Integrate temperature sensors and bake compensation curves into solver inputs | Drift trend exceeds 5 cm per day |
| Assembly variance reduces baseline accuracy | Medium | Medium | Design jigs for sensor placement and add automated production tests | Factory QA flags positional bias |

### Mitigation checklist

- [ ] Validate PLL timing stability across temperature chamber sweeps and log phase-noise metrics.
- [ ] Prototype modulation frequency hopping and measure cross-talk under mirrored-surface scenarios.
- [ ] Profile DMA throughput under worst-case burst loads; store benchmarking scripts and results alongside firmware modules.
- [ ] Extend the solver to ingest ambient temperature telemetry and re-fit compensation curves during calibration runs.
- [ ] Define assembly tolerances and integrate jig verification into manufacturing QA documentation.

## Outcome snapshot

Post-launch, the IR sensor array peripheral streams timestamped data at 200 Hz into the multilateration solver, delivering sub-10-centimetre pose estimates with confidence scoring. The directional remote’s sequenced beams provide unambiguous spatial cues while preserving standard bitstream semantics, enabling robots to interpret gestures and align themselves relative to operators. Operators calibrate the system in under five minutes via the CLI, dashboards visualise live pose and drift metrics, and follow-on experiments explore multi-remote interactions and ambient light resilience.
