# UWB Peripheral Rollout Plan

## Opening abstract

We are introducing ultra-wideband ranging to the Heart ecosystem so peripherals and hubs can localize each other within ±10 cm indoors. The rollout balances hardware integration of Qorvo DWM3001C modules, Zephyr/Nordic firmware updates, and automation platform changes that interpret high-resolution ranging data. **Why now:** Competitors are shipping UWB accessories, DW3000 module supply has stabilized, and customer research shows demand for room-level automations that current BLE solutions cannot provide reliably.

Primary stakeholders include the firmware platform crew, hardware engineering, automation experiences, telemetry, and privacy. Success hinges on validating accuracy in real homes, proving that installers can deploy anchors without RF surprises, and ensuring privacy messaging lands with pilot customers.

## Success criteria

| Outcome | Signal check | Owner |
| --- | --- | --- |
| Maintain ±10 cm 95th percentile ranging accuracy in pilot homes | Weekly Grafana dashboard aggregates `uwb_ranging_event` residuals \<0.1 m at P95 | Firmware lead |
| EVT anchor enclosures require zero antenna retunes | RF validation report shows \<1 dB mismatch across channels 5 and 9 | Hardware PM |
| Automations trigger within 150 ms median after zone entry | Automation latency telemetry links `uwb_ranging_event` to rule execution \<150 ms median | Experiences EM |
| Privacy expectations remain positive throughout beta | Interview synthesis doc shows ≥4/5 satisfaction on privacy comfort scale | Privacy research lead |

## Discovery phase checklist

- [ ] Audit hub MCU GPIO/SPI availability and update `docs/architecture/hub_io.md` with spare high-speed buses.
- [ ] Evaluate DWM3001C and DW3110 reference designs; document BOM, layout constraints, and antenna keep-out in a comparative sheet.
- [ ] Run bench tests with DWM3001C evaluation kits to measure SS-TWR accuracy, logging channel impulse response captures.
- [ ] Interview at least three pilot customers about indoor positioning privacy; summarize findings in `docs/research/privacy_guardrails.md`.
- [ ] Benchmark Zephyr UWB stack versus Qorvo reference firmware, recording CPU load, latency, and memory footprint.

## Build phase checklist

- [ ] Fork firmware branch enabling SS-TWR ranging service and BLE commissioning; include Nordic DFU path.
- [ ] Spin rev-A anchor PCB around DWM3001C with documented antenna keep-out and shield can placement; archive Altium source.
- [ ] Integrate `uwb_ranging_event` telemetry schema and end-to-end ingestion path; link to staging Grafana dashboard.
- [ ] Implement automation engine adapter that transforms UWB coordinates into zone entry/exit events with hysteresis.
- [ ] Prototype installer mobile app flow for anchor placement and calibration, including visual alignment aids.

## Rollout phase checklist

- [ ] Deploy UWB firmware to 10 employee pilot homes, capturing accuracy and battery metrics in a shared spreadsheet.
- [ ] Conduct RF validation sweep in anechoic chamber and document results in compliance tracker.
- [ ] Deliver support training session plus quick-reference FAQ hosted in Guru.
- [ ] Finalize FCC/ETSI submission package with lab booking confirmation and duty-cycle evidence.
- [ ] Publish customer-facing privacy and calibration FAQ on internal launch portal.

## Narrative walkthrough

Discovery begins with firmware and hardware sharing bench space to validate that the hub MCU can drive a DW3110 at 8 MHz over SPI without starving other peripherals. Simultaneously, the hardware team tests DWM3001C evaluation boards to confirm antenna clearance, while privacy researchers run structured interviews to surface concerns about indoor tracking. Weekly discovery standups collect metrics—CIR captures, CPU utilization, and interview quotes—and record them in the shared tracking sheet. By the end of discovery we will have a preferred module, a crisp view of firmware complexity, and documented privacy guardrails.

The build phase opens with firmware implementing HRP SS-TWR in Zephyr and instrumenting the Nordic DFU flow so anchors can update over BLE. Hardware spins the rev-A anchor PCB, integrates shield cans, and schedules S-parameter sweeps for the EVT run. Telemetry engineers deploy the `uwb_ranging_event` schema into staging, while automation engineers create a translation layer that maps trilaterated coordinates into zone entry events with hysteresis to avoid jitter. Installer experience designers produce a mobile tool that walks technicians through anchor placement with augmented overlays and verifies clock sync before they leave the site. Twice-weekly async updates in Notion track progress and escalate blockers—especially around RF layout and firmware timing.

Rollout overlaps with late build once firmware and hardware stabilize. Ten employee pilot homes receive the new anchors and firmware, each logging accuracy, latency, and battery drain. RF engineers conduct anechoic chamber sweeps to certify that the enclosure does not detune channels 5 and 9. Support leads run training sessions and publish troubleshooting guides so first-line agents can diagnose calibration issues. Compliance teams assemble FCC and ETSI submissions, including duty-cycle measurements captured during pilot sessions. Marketing and privacy leads craft customer-facing messaging, ensuring opt-in flows clearly state data handling policies.

## Signal propagation diagram

```
Tag Device      Hub Anchor      Telemetry Ingest      Automation Engine
    |                |                 |                       |
    |---- Blink ---->|                 |                       |
    |<-- Poll  ------|                 |                       |
    |---- Final ---->|                 |                       |
    |                |---- Event ----->|                       |
    |                |                 |---- Stream ---------> |
    |                |                 |<--- Rule Eval --------|
    |                |<--- Action -----|                       |
```

*Tip:* Capture the channel impulse response (CIR) for each ranging exchange and store it alongside the telemetry event. These samples speed up post-mortem analysis when accuracy drifts.

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| Antenna detuning in production enclosure | Medium | High | Schedule RF + ID review, prototype 3D-printed enclosures, run S-parameter sweeps | VNA sweep shows >3 dB mismatch |
| DW3001C supply disruption | Medium | High | Reserve buffer inventory, qualify DW3110 cost-down path | Supplier lead-time extension notice |
| Firmware power consumption exceeds battery targets | Medium | Medium | Implement adaptive ranging intervals, log battery trends in pilot homes | Pilot spreadsheet shows >10% daily drain |
| Privacy backlash during pilot | Low | Medium | Provide explicit opt-in, anonymize telemetry, co-review messaging with legal | Interview notes show discomfort or low satisfaction |
| Secure ranging key compromise | Low | High | Use secure element provisioning, monitor for anomalous round-trip variance | Telemetry flags repeated authentication failures |

### Mitigation checklist

- [ ] Lock manufacturing slots for primary and fallback module SKUs.
- [ ] Complete RF/ID enclosure review with thermal chamber validation booked.
- [ ] Ship firmware update enabling adaptive duty cycling before pilot expansion.
- [ ] Draft privacy comms playbook and route for legal approval.
- [ ] Exercise key rotation pipeline in staging with red-team validation.

## Outcome snapshot

Once the plan lands, Heart hubs and peripherals will maintain synchronized SS-TWR ranging with ±10 cm accuracy at the 95th percentile. Installers will rely on a guided mobile flow to position anchors, confirm calibration, and export compliance logs. Telemetry dashboards will expose accuracy, latency, and battery trends, giving the experiences team confidence to launch zone-based automations. Customers will opt into privacy-safe positioning, and compliance teams will hold FCC/ETSI approvals with documented duty-cycle evidence. Follow-on experiments will focus on multi-floor localization and automated calibration routines.
