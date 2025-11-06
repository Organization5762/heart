# Ultra-Wideband Peripheral Integration Options for Heart

## Executive summary

Ultra-wideband (UWB) enables centimeter-level ranging, giving Heart hubs and peripherals spatial awareness that BLE RSSI and Wi-Fi RTT cannot achieve consistently. Qorvo's DW3000 family raises the ceiling with IEEE 802.15.4z High Rate Pulse (HRP) support, improved power efficiency, and compatibility with FiRa and Apple Nearby Interaction ecosystems. This note summarizes hardware, antenna, firmware, and service integration considerations so the platform can estimate peer-to-peer distance within ±10 cm indoors while respecting tight power and privacy budgets.

## Problem statement

Heart needs a repeatable method for estimating the location of a battery-powered peripheral relative to a central hub or to other peripherals. Indoor multipath, orientation drift, and enclosure detuning regularly push Bluetooth-based techniques beyond ±1 m. UWB time-of-flight ranging remains resilient to multipath and supports cryptographic distance bounding. The research objective is to compare module and discrete options, outline firmware integration points, and flag backend and regulatory dependencies.

## Candidate hardware landscape

| Vendor | Part/module | Key traits | Integration notes |
| --- | --- | --- | --- |
| Qorvo | **DW1000**, **DWM1001** | Production-proven, 3.5–6.5 GHz, community firmware (Mynewt, Zephyr). No 802.15.4z. TX 130 mA. | Requires external MCU, larger power budget. Consider only if BOM pressure is extreme. |
| Qorvo | **DW3000** SoC (DW3110) and modules (**DWM3000**, **DWM3001C**) | IEEE 802.15.4z HRP, FiRa certified profiles, RX ~60 mA, integrated antennas in modules. | DWM3001C bundles nRF52833 + BLE, simplifies RF; discrete DW3110 mates with existing STM32/NRF boards. |
| NXP | **SR150/SR040** | Combines UWB, BLE, Cortex-M33. | Ecosystem thinner, dev kits available, but supply limited; evaluate only if co-packaged BLE is mandatory. |
| Pozyx | **Tag/Anchor kits** | Turnkey anchor network built on DW1000. | Useful for rapid proof-of-concept or lab benchmarking. |
| Nanotrack | **NTK3000** | DW3000-based modules with integrated MCU. | Attractive for ODM partnership if in-house RF resources are constrained. |

**Recommendation:** Prioritize DWM3001C for first hardware spin. The module ships with FCC/CE modular approvals, exposes both UWB and BLE, and allows reuse of Nordic SDK build infrastructure. Keep DW3110 on the radar as a cost-down once the RF design is proven.

## Antenna and mechanical considerations

- Maintain a 15 mm × 12 mm ground clearance under the ceramic antenna and avoid copper pour. Follow the DWM3001C hardware design guide for microstrip impedance.
- Shield the UWB section when co-located with switching regulators or high-speed digital lines. Early EVT builds should include S-parameter sweeps to catch detuning.
- Provide three-dimensional placement guidelines for industrial design so that anchors can be oriented orthogonally when triangulating tags.
- Budget plastic thickness below 2 mm directly above the antenna. Validate final enclosures with a near-field scanner or anechoic chamber sweeps.

## Firmware and stack integration

- **Operating system**: Zephyr already includes `drivers/uwb` for DW1000/3000. Nordic's nRF Connect SDK (NCS) bundles DW3000 drivers compatible with the DWM3001C onboard MCU.
- **Ranging protocol**: Implement IEEE 802.15.4z HRP Single-Sided Two-Way Ranging (SS-TWR) for low-latency interactions. Provide a switch to fall back to Double-Sided TWR when multipath dominates.
- **Synchronization**: Anchors require \<1 µs clock drift. Use Periodic Sync Frames (PSF) or rely on BLE-connected time sync when the hub acts as master.
- **Commissioning**: Boot the DWM3001C via Nordic DFU over BLE; include a BLE advertising payload that exposes firmware version and supported channels.
- **Security**: Enable STS (Secure Time Stamping) with AES-128 keys provisioned in the Nordic secure bootloader. Pairing can bootstrap via existing Heart manufacturing flows.
- **Telemetry**: Emit raw timestamps and computed ranges into a new protobuf schema (`uwb_ranging_event`). Annotate records with channel, preamble index, and diagnostics (CIR peak, FP quality) for analytics.

## Localization algorithms and software hooks

- Start with centralized trilateration inside the hub. Compute distances to at least three anchors and solve via nonlinear least squares (e.g., Levenberg–Marquardt) using R^3 coordinates.
- Wrap results in a Kalman filter that fuses IMU accelerometer data when available. Treat UWB ranges as absolute position updates and IMU integration as prediction steps.
- For peer-to-peer interactions (peripheral-to-peripheral), expose a "tag" firmware mode that allows a device to act as both responder and initiator. Evaluate Qorvo's ranging library for low-level waveform timing management.
- Integrate with Heart's automation engine by creating presence zones. When a device's estimated coordinate enters a zone, fire an event identical to current geofence triggers.
- Prototype cloud-side analytics to detect drift. When residuals exceed ±15 cm, prompt recalibration or anchor repositioning.

## Cloud and service touchpoints

- Extend the telemetry ingestion pipeline to support UWB payloads. Ensure the event stream includes device IDs, session IDs, and security metadata for traceability.
- Build dashboards that plot range statistics, filter by firmware version, and visualize anchor geometry per install.
- Update privacy controls so users can opt into or out of fine-grained localization. Provide transparency logs for data retention and anonymization policies.

## Power and duty cycle budgeting

- DW3000 tags draw ~60 mA in RX and ~115 mA in TX. With a 100 ms SS-TWR interval and 2 ms active window, average current drops near 2 mA. Adjust polling frequency dynamically based on motion or automation urgency.
- Enable deep sleep between ranging sessions. Nordic's nRF52833 on DWM3001C supports \<5 µA sleep; ensure interrupts wake only when necessary.
- Model thermal load with 10% duty cycle bursts. Place UWB modules away from Li-ion cells to maintain \<85 °C junction temperature.

## Regulatory and regional compliance

- UWB falls under FCC Part 15 Subpart F. DWM3001C modular approval simplifies certification, but final products still require unintentional radiator testing.
- ETSI EN 302 065 governs EU operation. Channel 5 is restricted in India; maintain a region-aware channel map and disable unsupported bands at runtime.
- Capture duty cycle and Effective Isotropic Radiated Power (EIRP) metrics during validation. Store results in compliance documentation for audit readiness.

## Security posture

- Mandate mutual authentication via STS; reject frames with unexpected sequence numbers or clock skew.
- Monitor round-trip time variance to detect relay attacks. Combine with BLE proximity as a secondary factor for high-stakes automations.
- Ensure firmware updates enforce secure boot and signed images. Align with Heart's existing provisioning pipeline.

## Open questions and next steps

- Does the current hub MCU expose a free high-speed SPI capable of 8 MHz+ for DW3110 integration if we choose the discrete route?
- Should we embed UWB into existing peripherals (thermostats, switches), or release dedicated anchors and tags?
- What manufacturing fixtures are required for factory calibration of antenna delays and crystal trimming?
- How do we surface calibration workflows to installers without overwhelming them? Consider augmented reality alignment aids or guided mobile apps.

## Recommended experiments

1. Order DWM3001C evaluation kits and validate SS-TWR accuracy across varied multipath environments. Log channel impulse response (CIR) data for future machine learning enhancements.
1. Benchmark Nordic's UWB stack against Qorvo's reference to quantify latency, CPU usage, and memory footprint.
1. Prototype backend processing with simulated ranges to evaluate trilateration convergence and automation latency.
1. Run privacy workshops to test messaging around indoor positioning. Capture responses to opt-in flows and anonymization promises.

## References

- Qorvo DW3000 product brief and hardware design guidelines (downloaded 2024-05-12).
- IEEE 802.15.4z HRP ranging specification, Annex E.
- Nordic Semiconductor nRF Connect SDK documentation (UWB preview branch).
- Internal Heart automation engine specification (`docs/architecture/automation_engine.md`).
