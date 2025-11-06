# Bluetooth Peripheral Reverse Engineering Playbook

**Opening abstract.** This plan outlines the workflow for characterising arbitrary Bluetooth Low Energy (BLE) peripherals so that Heart can publish structured driver classes under `drivers/bluetooth/`. The primary operators are firmware analysts and integration engineers who must transform a paired peripheral into reproducible telemetry streams. **Why now:** product teams are onboarding wellness trackers and industrial sensors faster than bespoke reverse engineering can keep up, so we need a standard pipeline that reduces ramp-up time and ensures research notes stay synchronised with the codebase.

**Success criteria**

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Capture complete GATT map and advertisement metadata within 48 hours of device receipt | Checklist artefacts committed to `docs/research/` with timestamped packet captures | Discovery lead |
| Generate protocol hypotheses with round-trip verification harness | Pytest module under `tests/bluetooth/` that exercises inferred characteristics without regressions | Implementation lead |
| Produce production-ready driver skeleton | New classes in `drivers/bluetooth/` passing `make check` and `make test` | Integration engineer |
| Publish operator guide for sustained maintenance | Markdown note in `docs/runtime/` with monitoring dashboards linked | Reliability owner |

**Task breakdown**

***Discovery phase***

- [ ] Inventory radio profiles and physical interfaces; log FCC IDs, chipset markings, and supported transports in `docs/research/bluetooth_device_dossier.md`.
- [ ] Acquire manufacturer apps and firmware images; archive APK/IPA and updater binaries in the shared `experimental/bluetooth/artifacts/` bucket.
- [ ] Baseline device behaviour using an isolated mobile host; record advertisement intervals and connection requirements via `btmon` traces stored under `docs/research/captures/`.
- [ ] Document operator constraints (battery, environmental triggers, authentication) alongside hypotheses in the discovery note.

***Protocol capture phase***

- [ ] Configure sniffing stack using `btlejack` or `nrf-sniffer` depending on chipset inference; store configuration scripts in `scripts/bluetooth/sniff/`.
- [ ] Capture pairing sequences, MTU negotiation, and characteristic read/write cycles; export to `.pcapng` and annotate using Wireshark display filters.
- [ ] Build or adapt Wireshark Lua dissectors for device-specific frames; version control them in `scripts/bluetooth/wireshark_plugins/` and document expected fields in the discovery note.
- [ ] Derive preliminary attribute taxonomy (services, characteristics, descriptors) and compile into a CSV saved in `docs/research/bluetooth/<device>_gatt.csv`.
- [ ] Flag encrypted channels or proprietary security as risks, noting required tooling (e.g. MITM proxies) in the research log.

***Implementation phase***

- [ ] Translate GATT map into Python dataclasses under `drivers/bluetooth/<device>/characteristics.py`, encoding UUIDs, value formats, and permissions.
- [ ] Implement connection orchestration in `drivers/bluetooth/<device>/client.py` leveraging the shared BLE transport abstractions in `src/heart/io/bluetooth.py`.
- [ ] Write protocol hypotheses as parametrised tests in `tests/bluetooth/test_<device>_protocol.py`, replaying captured packets through emulated adapters.
- [ ] Generate documentation via `scripts/render_code_flow.py` to update `docs/code_flow.md` if transport sequencing diverges from existing models.

***Validation phase***

- [ ] Run `make check` and `make test` to ensure drivers meet formatting and behavioural expectations before merging.
- [ ] Exercise long-lived sessions with `experimental/bluetooth/replay.py` to confirm reconnection logic and error handling.
- [ ] Collect metrics by hooking driver outputs into the staging telemetry pipeline; verify schemas align with downstream consumers in `docs/runtime/telemetry_contracts.md`.
- [ ] Conduct operator handoff review, capturing outstanding questions and future experiments in the runtime note.

**Narrative walkthrough**

The playbook begins with physical and radio reconnaissance so engineers can anchor the investigation in verifiable artefacts. Early cataloguing of chipsets and firmware gives us predictive power when selecting sniffers or transport shims, and ensures the discovery note becomes a single source of truth. Once the baseline behaviour is understood, the protocol capture phase emphasises reproducible packet captures, annotated with the same filters that analysts will reuse during debugging. This enables rapid iteration across teams because the CSV taxonomy, captures, and hypotheses live side-by-side.

Implementation converts raw observations into formalised code. By mapping GATT attributes into dataclasses and client orchestration modules, we reinforce our coding conventions while making it trivial to stub drivers during integration tests. Tests replay real captures to validate hypotheses, closing the loop between observation and code. If the connection choreography deviates from the repository's baseline assumptions, rendering the updated code flow keeps architecture documentation honest.

Validation ensures production readiness. Running the standard `make` pipelines avoids regression surprises, while replay harnesses provide soak coverage for intermittent bugs. Integrating telemetry early lets observability owners verify that data contracts stay compatible with dashboards and alerts. The operator review formalises the handoff, ensuring ongoing ownership is clear.

> Tip: Treat Wireshark plugins as first-class artefacts. Custom dissectors surface derived fields—such as scaling factors or checksum states—directly in packet views, cutting protocol hypothesis time in half and giving reviewers a reusable lens for future firmware drops.

**Signal capture sequence**

```
[Peripheral] --advertisements--> [Host sniffer]
[Host sniffer] ==captures==> [Packet archive]
[Packet archive] --annotations--> [GATT taxonomy]
[GATT taxonomy] --codegen templates--> [Driver dataclasses]
[Driver dataclasses] --pytest replay--> [Validation reports]
```

**Risk analysis**

| Risk | Probability | Impact | Mitigation strategy | Early warning signals |
| --- | --- | --- | --- | --- |
| End-to-end encryption blocks characteristic inspection | Medium | High | Capture application-layer traffic via instrumented companion app; request debug keys from vendor when possible | Repeated GATT error responses; inability to decrypt notifications |
| Proprietary transports masquerade as BLE | Low | High | Validate advertisement flags and PHY before committing; prepare 2.4 GHz spectrum scans | Advertisements missing GATT UUIDs; inconsistent connection intervals |
| Toolchain drift or driver incompatibilities | Medium | Medium | Version pin sniffing tools in `uv.lock`; run nightly CI on sample captures | Repeated failures in `make check`; outdated pip dependencies |
| Insufficient replay fidelity for automated tests | Medium | Medium | Expand replay harness to simulate timing jitter and packet loss; add integration fixtures | Flaky pytest results; divergence between lab and field telemetry |

Mitigation checklist

- [ ] Maintain vendor contact list with escalation paths in `docs/runtime/vendor_relations.md`.
- [ ] Automate capture-to-CSV pipeline via `scripts/bluetooth/pcap_to_gatt.py` to reduce manual errors.
- [ ] Schedule quarterly toolchain audits, rotating owners across the BLE guild.
- [ ] Prototype packet fuzzing harness to stress-test notification parsers prior to release.

**Outcome snapshot**

When this plan lands, every new BLE peripheral ships with an auditable dossier, reproducible packet archives, and a driver package under `drivers/bluetooth/` that conforms to repository standards. Engineers will spin up protocol hypotheses in hours, not weeks, because discovery artefacts, replay tests, and runtime documentation flow through a consistent pipeline. Operational teams inherit clear monitoring contracts, enabling them to detect device regressions without reverse engineering expertise.
