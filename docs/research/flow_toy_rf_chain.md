# Flow Toy RF Research Chain

## Research objective

Characterize the passive radio emissions from commercially available light-up flow toys, reconstruct their protocol, and design a bidirectional control interface that Heart can own. This chain establishes repeatable discovery, decoding, and control validation so contributors can iterate without rediscovering foundational RF details.

## Chain overview

1. **Device fingerprinting** – Document the toy lineup, firmware revisions, and companion app versions. Capture FCC IDs and PCB photos to infer RF front-ends and antenna topology.
1. **Spectrum reconnaissance** – Sweep 100 kHz–6 GHz with a wideband SDR. Correlate peaks with toy activity and annotate center frequencies, bandwidth, and modulation cues (e.g., GFSK, BLE advertising).
1. **Capture pipeline** – Configure a reproducible IQ capture flow using GNU Radio Companion (GRC) scripts checked into `experimental/rf/flow_toys/`. Provide presets for HackRF One and PlutoSDR including gain, sample rate, and decimation settings.
1. **Burst extraction** – Feed raw IQ into Universal Radio Hacker or custom Python notebooks that implement energy detection, preamble search, and symbol timing recovery. Output decoded symbol streams into `npz` datasets for collaborative analysis.
1. **Protocol reconstruction** – Apply differential analysis by aligning captured bursts with annotated app actions. Use Kaitai Struct or Construct to define tentative frame schemas and verify them against multiple captures. Track hypotheses in `docs/research/logs/flow_toys/` with timestamped entries.
1. **Security assessment** – Evaluate whether payloads incorporate encryption or pairing handshakes. For BLE-based toys, use `btproxy` or `nRF Sniffer` to inspect LTK exchange. For proprietary 2.4 GHz links, examine checksums for cryptographic strength and attempt known-plaintext attacks.
1. **Transmitter prototyping** – Once frame structure is understood, implement a replay tool using `pyspinel`, `nRF ESB` libraries, or raw PHY generation in GNU Radio. Validate on-air using a shielded enclosure to avoid interference.
1. **Runtime integration** – Build a `FlowToyLink` abstraction in `src/heart/peripheral/flow_toy/` that can operate in capture-only or full-duplex modes. Integrate telemetry parsing and command emission with the existing event bus/state store infrastructure.
1. **Regression harness** – Create automated tests that replay captured IQ files and assert deterministic decoding. Mirror those tests with hardware-in-the-loop runs triggered via `make flow-toy-hil` to ensure the transmitter path stays aligned with firmware updates.
1. **Field validation** – Deploy a portable kit (laptop + SDR + selected transceiver) to live rehearsals, capturing RF traces alongside operator notes. Feed findings back into the regression harness to model real-world multipath and interference.

## Software toolchain

| Layer | Tooling | Repository location |
| --- | --- | --- |
| SDR configuration | GNU Radio Companion flows (`flow_toy_capture.grc`) | `experimental/rf/flow_toys/` |
| Burst analysis | Python notebooks (`burst_characterization.ipynb`) using `numpy`, `scipy`, `scikit-dsp-comm` | `docs/research/notebooks/flow_toys/` |
| Protocol spec | Kaitai Struct (`flow_toy_frame.ksy`) with generated Python parser | `src/heart/protocols/flow_toy/` |
| Runtime bridge | Python driver + CFFI bindings for transceiver firmware | `src/heart/peripheral/flow_toy/driver.py` |
| Test harness | Pytest suite with `pytest-sdr` fixtures and capture fixtures | `tests/peripherals/flow_toy/` |
| Telemetry dashboard | Grafana + `prometheus-client` exporter summarizing packet quality metrics | `experimental/telemetry/flow_toys/` |

## Hardware platform options

| Role | Candidate | Rationale | Integration notes |
| --- | --- | --- | --- |
| Wideband capture | HackRF One | 1–6 GHz coverage, community tooling, supported by URH | Requires external TCXO upgrade for stability |
| High-fidelity capture | Ettus B205mini-i | Better dynamic range, UHD support | Higher cost; use when modulation demands precision |
| BLE/proprietary TX/RX | Nordic nRF52840 Dongle | Native BLE + ESB support, open-source sniffer firmware | USB form factor integrates with existing host tools |
| Multi-protocol TX/RX | TI CC2652P LaunchPad | Amplified 2.4 GHz radio, multiprotocol SDK | Needs firmware build via Code Composer or `tiarmclang` |
| Wi-Fi / 802.15.4 bridge | ESP32-C6 DevKitC | Combines Wi-Fi telemetry with BLE fallback | Custom RF path requires IDF 5.1+; ensure coexistence settings tuned |
| Custom PHY experimentation | LimeSDR Mini 2.0 | Flexible LMS7002M transceiver for arbitrary waveforms | Requires USB 3.0 host and LimeSuite calibration before capture |

## Interfaces & firmware strategy

- **Passive capture mode.** SDR streams IQ over USB to the host laptop. GNU Radio demodulates to symbols and forwards newline-delimited hex packets via ZeroMQ. The Heart runtime subscribes to the socket and records packets for offline analysis.
- **Active control mode.** A USB-attached transceiver (nRF52840 or CC2652) runs custom firmware exposing a UART command channel. Heart sends serialized frame descriptors (address, opcode, payload, checksum), and firmware handles PHY timing. Responses are echoed back to Heart for logging.
- **Safety interlocks.** Firmware enforces a whitelist of permitted frequencies and duty cycles. Host software requests a session lease before enabling transmit, and leases auto-expire after 120 seconds of inactivity.
- **Data retention.** Persist IQ files, decoded payload CSVs, and firmware images in the RF artifact bucket with SHA-256 manifests. Tag each upload with the regression harness version to ensure replay parity.

## Open questions

1. Do vendors rotate device addresses or session keys after each app pairing? Requires longitudinal captures post power-cycle.
1. Are there fallback IR or magnetic sensors for legacy flow toys that could serve as alternative control paths?
1. What minimum timing precision does choreography require? Need latency studies comparing BLE write-without-response versus custom GFSK frames.

## Next steps

- Draft detailed capture scripts referencing specific GNU Radio blocks and publish them with example IQ files.
- Prototype the ZeroMQ bridge and integrate it into the sandbox demo for passive telemetry visualization.
- Begin RF compliance review to ensure future transmit testing can occur within lab constraints.
- Stand up nightly decoder regression jobs in CI that consume the latest capture artifacts and post dashboards to the telemetry workspace.
