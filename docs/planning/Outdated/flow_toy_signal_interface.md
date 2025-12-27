# Flow Toy Signal Capture & Control Plan

## Abstract

Flow toys such as pixel whips and LED poi broadcast status telemetry over low-power radios so companion apps can synchronize color patterns. We aim to first observe those passive emissions, then mature into a full duplex integration where Heart can both read and control the toys. The primary operators are the hardware integration team and the runtime maintainers who manage device orchestration.

**Why now.** Multi-output experiences are central to Heart's roadmap. Flow toy control delivers the first lighting peripheral able to mirror Heart's state. Establishing a capture-to-control pipeline now lets us validate spectrum use, message formats, and latency while the hardware group prototypes the next wave of ambient devices.

## Success criteria

| Target behaviour | Observable signal | Validation owner |
| --- | --- | --- |
| Reliable passive capture of toy telemetry packets within 3 m | Replayed IQ captures reconstructed into packets with \<5% packet loss during 10-minute capture windows | RF tooling lead |
| Accurate protocol reverse-engineering | Decoder produces fields matching vendor mobile app logs with \<2% variance over 100 messages | Embedded architect |
| Bidirectional control from Heart runtime | Heart orchestrator toggles toy modes with end-to-end latency \<150 ms | Runtime maintainer |
| Safe multi-device arbitration | Two toys driven concurrently retain independent addressing without command bleed-over across 30 test cycles | QA automation |

## Phase breakdown

### Discovery – capture and protocol reconnaissance

- [ ] Inventory available flow toys, document hardware revisions, and confirm their companion transports (BLE, proprietary 2.4 GHz, Wi-Fi).
- [ ] Collect FCC filings or teardown notes for PCB photos, antenna design, and MCU choices to inform spectrum scans.
- [ ] Acquire SDR samples (HackRF + GQRX or PlutoSDR + SoapySDR) across 2.4 GHz and sub-GHz bands while toys operate in default modes.
- [ ] Use `inspectrum`/`Universal Radio Hacker` to segment bursts, identify preambles, and estimate symbol rates.
- [ ] Align captured messages with mobile app actions to map cadence and infer directionality.
- [ ] Establish a capture log in `docs/research/logs/flow_toys/captures.md` summarizing date, toy firmware, antenna chain, gain, and environment noise floor measurements.
- [ ] Build an RF calibration checklist (attenuator values, LNA state, clock source) to keep multi-session captures reproducible.

### Implementation – decoding and runtime integration

- [ ] Build a Python-based demodulation toolchain (GNU Radio flowgraph + custom demod script) that outputs timestamped payloads.
- [ ] Reverse-engineer frame structure: sync word, address fields, checksums, and payload encoding; document findings in `docs/research/`.
- [ ] Prototype a `FlowToyReceiver` that ingests demodulated payloads over a socket or file interface and publishes events on the input bus.
- [ ] Evaluate candidate transceivers (nRF52840, TI CC2652, ESP32-C6) for transmit capability at the discovered modulation scheme.
- [ ] Design a command serializer mirroring decoded frames, supporting sequence numbers and HMAC/signature fields if detected.
- [ ] Define automated regression fixtures in `tests/peripherals/flow_toy/` that replay captures and assert decoder stability before firmware commits merge.
- [ ] Outline a telemetry schema contract in `docs/runtime_interfaces.md` so choreography tooling can subscribe to normalized toy state.

### Validation – closed-loop testing & UX handoff

- [ ] Assemble a test jig with two flow toys, the SDR capture device, and the selected transceiver dev board for transmission tests.
- [ ] Run soak tests measuring Heart-to-toy latency, error rates, and interference when co-located with Wi-Fi/Bluetooth devices.
- [ ] Integrate multi-toy control scenarios into the sandbox demo, logging state transitions and verifying deterministic arbitration policies.
- [ ] Document operator workflows covering capture setup, firmware flashing, and troubleshooting in `docs/ops/flow_toys.md`.
- [ ] Align choreography cues with UX/audio stakeholders once control paths are stable.
- [ ] Produce a compliance readiness packet summarizing channel plans, calculated duty cycles, and certification requirements for the selected transceiver.
- [ ] Schedule a live rehearsal in the experience lab with production lighting to validate human-perceived synchronization and gather UX sign-off notes.

## Narrative walkthrough

Discovery anchors the plan by capturing real radio activity before any code is written. FCC artifacts narrow candidate bands, and IQ recordings aligned with app actions reveal whether we face BLE, Enhanced ShockBurst, or custom GFSK. That baseline prevents premature assumptions about pairing or crypto.

Implementation begins once payload captures are repeatable. GNU Radio handles filtering, but we export symbol streams into Python so contributors can iterate without the GUI. Frame structure notes become the contract for runtime integration as the `FlowToyReceiver` feeds the event bus. In parallel we evaluate Nordic nRF52840, TI CC2652, and Espressif ESP32-C6 options against modulation support, stack maturity, and firmware pipeline fit.

Validation closes the loop. A bench jig replays Heart commands while the SDR monitors on-air responses to verify legal waveforms. Long-duration trials quantify packet loss and interference susceptibility. Multi-device arbitration tests guarantee the command serializer respects per-toy addresses, and documentation plus UX coordination ensure operators can stage synchronized shows quickly.

> **Note**
> Store every validated capture, decoder release, and firmware build artifact in `s3://heart-rf/flow-toys/` with semantic version tags so field teams can stage regressions without rerunning the entire discovery workflow.

## Data path overview

```
[Flow Toy Radio] --(GFSK bursts)--> [SDR Frontend] --(IQ stream)--> [GNU Radio demod]
       |                                                         |
       |                                                     (UDP/TCP)
       |                                                         v
       +<--(Command frames)-- [Transceiver Dev Board] <-- [Heart FlowToyDriver]
```

## Hardware evaluation matrix

| Chipset | Protocol coverage | Max TX power | Dev ecosystem | Notable constraints |
| --- | --- | --- | --- | --- |
| Nordic nRF52840 | BLE 5.0, 2.4 GHz proprietary (ESB) | +8 dBm | Zephyr RTOS, nRF Connect SDK, mature packet sniffer firmware | Requires precise matching network; limited open tooling for non-BLE proprietary stacks |
| TI CC2652R7 | BLE, Zigbee, Thread, 2.4 GHz OOK/FSK | +5 dBm | TI SimpleLink SDK, SmartRF Studio | Zigbee-centric examples; custom modulation needs RF Studio scripting |
| Espressif ESP32-C6 | BLE 5, Wi-Fi 6, 802.15.4 | +20 dBm (Wi-Fi), +10 dBm (BLE) | ESP-IDF, open-source MAC layers | Custom GFSK requires co-processor or firmware patching |
| ADI ADF7242 + MCU | 2.4 GHz O-QPSK/FSK with raw mode | +4 dBm | Registers exposed for direct PHY manipulation | Requires separate MCU; limited community support |
| Silicon Labs EFR32MG24 | Multi-protocol with advanced radio configurator | +10 dBm | Simplicity Studio tooling, strong Thread/Zigbee support | Proprietary tooling on macOS; licensed RAIL stack |

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| Protocol uses encrypted BLE with rolling keys | Medium | Blocks command injection | Monitor BLE pairing traffic for LTK exchanges; prepare to leverage MITM via BLE proxy and request vendor debug firmware | Companion app demands re-pair every session |
| SDR capture quality insufficient in noisy venues | High | Packet loss >10% | Deploy band-pass filters and shielded enclosures; schedule captures in RF isolation chamber before field trials | IQ recordings show inconsistent preamble detection |
| Transmit experiments violate regional RF regulations | Low | Regulatory exposure | Use shielded box for initial TX tests, document channel/frequency, adhere to FCC Part 15 limits | SDR waterfall shows out-of-band splatter |
| Toy firmware updates shift protocol | Medium | Decoder obsolescence | Automate nightly captures from toys with auto-update enabled; add version fingerprinting to frame parser | App release notes mention RF fixes |
| Selected transceiver cannot meet real-time latency budget | Medium | Degraded choreography alignment | Bench-mark latency with loopback firmware before integration; retain alternate chipset for fallback | Latency logs exceed 150 ms in soak test |

**Mitigation checklist**

- [ ] Validate BLE security posture with `btproxy` before investing in custom PHY tooling.
- [ ] Budget for an RF isolation enclosure and calibrated attenuators in Q2 hardware spend.
- [ ] Draft a regulatory compliance note covering duty cycle, frequency plan, and conducted power limits.
- [ ] Implement frame versioning in the Heart runtime so protocol shifts trigger alerts.
- [ ] Maintain parallel firmware branches for Nordic and TI development kits until latency and compliance benchmarks converge.

## Outcome snapshot

Once delivered, Heart will ingest flow toy telemetry through a dedicated driver that feeds the input event bus and state store. Operators can toggle choreographed modes from the runtime while a paired transceiver board maintains RF compliance and addressing. We will have reproducible capture scripts, a validated decoder, and a transmitter integration that extends Heart's output channel repertoire beyond audio and screens.
