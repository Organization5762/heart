# MIDI Peripheral Converter Implementation Plan

## Abstract

We will deliver a converter that listens to the Heart peripheral event bus, renders MIDI messages across USB, DIN, and virtual transports, and ingests inbound MIDI streams back into the bus. The work targets creative coders and performers who want biometric and gestural inputs to influence external instruments while letting external controllers steer Heart automations without bespoke wiring. **Why now:** existing peripherals already emit normalized `Input` events through the shared `EventBus`, but no downstream consumer bridges those signals into an industry protocol, and operators rely on ad-hoc scripts to read MIDI back into Heart. Shipping the converter as a bidirectional bridge unlocks hardware integration pilots and human-in-the-loop performances that are currently blocked. 【F:src/heart/peripheral/core/event_bus.py†L22-L68】【F:src/heart/peripheral/core/manager.py†L20-L104】【F:src/heart/peripheral/core/__init__.py†L13-L56】

## Success criteria

| Target behaviour | Verification signal | Owner |
| --- | --- | --- |
| Converter streams MIDI CC and note events derived from accelerometer and switch peripherals with \<10 ms added latency | Automated integration test asserts message timestamps against monotonic clock while replaying recorded `Input` fixtures | Audio systems engineer |
| Inbound MIDI messages generate normalized `Input` events that downstream subscribers handle without modification | Loopback test injects MIDI note/CC data and verifies event bus observers receive expected payloads | Automation engineer |
| Configuration schema lets operators enable/disable converter, choose transport, select mapping profile, and define inbound routing without code changes | CLI smoke test loads YAML overrides and observes converter toggling and routing updates at runtime | Runtime maintainer |
| Transport adapters recover from disconnects within 2 seconds without crashing the peripheral threads | Fault-injection test simulates USB removal and checks for automatic reconnection logs | Device reliability engineer |
| Documentation provides mapping examples and troubleshooting guidance | Tech writer verifies new docs in `docs/research/` and `docs/planning/` plus runtime README updates | Developer experience lead |

## Phase breakdown and checklists

### Discovery

- [ ] Confirm priority peripherals (switch, accelerometer, heart rate) with program stakeholders.
- [ ] Audit `PeripheralManager` startup sequence to ensure converter can attach after detection completes. 【F:src/heart/peripheral/core/manager.py†L20-L118】
- [ ] Benchmark `EventBus` publish frequency under combined peripheral load to estimate worst-case throughput. 【F:src/heart/peripheral/core/event_bus.py†L22-L68】
- [ ] Evaluate candidate MIDI libraries (`mido`, `python-rtmidi`, ALSA bindings) for latency, licensing, duplex support, and deployment footprint.
- [ ] Define initial mapping templates for CC, note, and pitch-bend conversions sourced from research note scenarios.
- [ ] Inventory automation subsystems that should consume inbound MIDI events and capture their latency budgets.

### Implementation

- [ ] Introduce `MidiConverter` module under `heart/peripheral` with constructor accepting `EventBus` and configuration payload.
- [ ] Provide wildcard and scoped subscription helpers that map to `EventBus.subscribe` without starving other listeners. 【F:src/heart/peripheral/core/event_bus.py†L22-L68】
- [ ] Build mapping engine supporting scaling, smoothing, and stateful note gates using the bus `StateStore`.
- [ ] Implement transport adapters: USB (via `python-rtmidi`), virtual port (using OS abstraction), and placeholder DIN (mocked until hardware lands).
- [ ] Add inbound MIDI listener that parses bytes into `Input` events, tags their origin, and guards against feedback loops.
- [ ] Wire configuration loader to extend `Configuration` schema so `heart manage` CLI can flip transports, profiles, and inbound routing tables. 【F:src/heart/peripheral/core/manager.py†L63-L107】
- [ ] Register converter inside `PeripheralManager` startup path after all peripherals attach to ensure it hears every event and exposes inbound listeners. 【F:src/heart/peripheral/core/manager.py†L20-L118】
- [ ] Add CLI diagnostics command that prints active mappings, transport status, and inbound routing state.

### Validation

- [ ] Unit tests cover mapping math, ensuring sensor ranges map into MIDI 0–127 and velocity envelopes behave deterministically.
- [ ] Integration tests spin up fake bus, push fixture events, and assert serialized MIDI bytes for multiple profiles while injecting inbound MIDI to confirm normalized events.
- [ ] Hardware-in-the-loop scenario uses loopback MIDI device to confirm latency budget, reconnection handling, and inbound control fidelity.
- [ ] Reliability soak test runs continuous event replay plus MIDI controller sweeps for one hour and checks for missed events or crashes.

## Narrative walkthrough

We begin by clarifying scope with stakeholders to avoid over-engineering mappings that will not see immediate use. Discovery focuses on measuring existing event bus throughput, enumerating library dependencies, and confirming which automation surfaces expect inbound MIDI so we can set realistic latency targets for both directions. Benchmarking also reveals whether we need asynchronous queues from the outset.

Implementation starts once we have a vetted library choice. We place the converter beside other peripherals so it can reuse configuration patterns and logging. The converter registers a wildcard subscription to the event bus, but also exposes profile-specific subscribers to minimize overhead when only a subset of events matter. Mapping logic lives in a dedicated component with deterministic scaling functions so QA can verify outputs without hardware. In parallel, the inbound listener normalizes MIDI into `Input` events, tags their origin, and observes backpressure metrics before publishing to the bus.

Transport adapters abstract USB, virtual, and future DIN connections. We prioritize USB because it enables immediate desktop integration, while the DIN adapter ships as a stub that defers hardware signaling to follow-up work. Shared adapters expose bidirectional interfaces so the same transport handles output and input when hardware permits. Configuration hooks integrate with the existing `Configuration` helper so operators can toggle behaviours and define inbound routing without editing code. Finally, we add a CLI diagnostic command to surface which mappings are active, which inbound routes are enabled, and how transports are performing, assisting field debugging.

Validation combines automated and manual checks. Unit tests exercise mapping math, note gate state machines, and inbound parser edge cases. Integration tests replay recorded `Input` fixtures, inspect emitted MIDI bytes, and feed in controller streams to ensure downstream subscribers receive normalized events. Hardware tests use loopback devices to measure end-to-end latency in both directions and confirm that disconnects are handled gracefully. A soak test ensures long-running sessions remain stable even when inbound controllers send dense data.

## Visual reference

| Component | Responsibility | Interfaces |
| --- | --- | --- |
| `MidiConverter` | Subscribes to `EventBus`, orchestrates mapping, transport, and inbound routing | Consumes `Input` events, depends on `StateStore`, emits MIDI packets, publishes MIDI-derived events |
| Mapping engine | Applies templates, scaling, smoothing, and gating | Receives normalized events, returns MIDI message structs |
| Transport adapters | Serialize MIDI messages, deliver to hardware/virtual endpoints, and receive input | Provide `open`, `send`, `receive`, `close` methods for USB, virtual, DIN |
| Inbound listener | Parses MIDI input, deduplicates feedback, publishes events | Consumes raw MIDI bytes, emits `Input` instances |
| Configuration layer | Loads profiles, transport selection, runtime toggles, and inbound routing | Extends `Configuration` schema, integrates with CLI |

## Risk analysis

| Risk | Probability | Impact | Mitigation strategy | Early warning signal |
| --- | --- | --- | --- | --- |
| MIDI library introduces heavy dependencies or fails on Raspberry Pi | Medium | High | Prototype with minimal wrappers; provide fallback pure-Python serializer | Installation errors or import failures during smoke test |
| Event bus callback blocks peripheral threads, causing missed sensor data | Medium | High | Move MIDI serialization to worker thread with bounded queue | Log warnings about slow subscriber execution |
| Transport disconnects overwhelm reconnection logic | Low | Medium | Add exponential backoff and watchdog timers for reconnect attempts | Repeated failure logs or queue growth metrics |
| Mapping complexity confuses operators | Medium | Medium | Ship opinionated starter profiles and documentation with diagrams | Support tickets asking for configuration clarification |
| Inbound MIDI floods saturate event bus consumers | Medium | Medium | Rate-limit inbound publishing, expose queue metrics, and allow per-route throttling | Observability dashboards show sustained inbound queue depth |
| Hardware DIN output unavailable for initial release | High | Low | Publish stub adapter with clear TODO; plan follow-up hardware sprint | Planning review identifies missing hardware BOM |

### Mitigation checklist

- [ ] Implement queue depth metrics and log when subscriber processing exceeds 5 ms.
- [ ] Wrap transport send operations in retry helpers with configurable backoff.
- [ ] Write operator guide covering profile editing, transport selection, and inbound routing.
- [ ] Document hardware dependencies and flag DIN adapter as experimental in release notes.
- [ ] Add inbound throughput alerts that trigger when queue depth exceeds thresholds for 10 seconds.

## Outcome snapshot

After landing this work, any Heart deployment can translate peripheral activity into MIDI in under 10 ms without manual scripts while simultaneously reacting to inbound controller data. Operators toggle mappings and inbound routes through configuration files or CLI, and the system auto-recovers from transient transport failures. External synthesizers, DAWs, or lighting rigs respond to switches, accelerometers, and heart-rate data streamed by the existing peripheral stack, and performers can inject MIDI gestures that steer Heart automations. The bidirectional bridge creates a foundation for future creative programs and research experiments.
