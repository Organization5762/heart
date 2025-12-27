# Bluetooth Cube Scene Orchestration Plan

## Abstract

This plan describes how to capture the state of a Bluetooth-enabled Rubik's Cube and transform that telemetry into lighting or multimedia scenes. The work targets the show-control service that already orchestrates venue lighting cues. Our primary users are interactive experience designers who need reliable, low-latency cues derived from cube interactions. **Why now:** audience participation demos are bottlenecked by manual triggering; the cube provides a rich, sensor-backed interface that can synchronise with existing control timelines.

## Success criteria

| Target behaviour | Observable signal | Validation owner |
| --- | --- | --- |
| Cube orientation and twist events arrive within 150 ms of physical movement. | Timestamped BLE characteristic updates logged by the telemetry service. | Realtime systems engineer |
| Scene mapping rules fire deterministically for at least 50 scripted cube states. | Replay harness showing correct scene IDs for reference cube traces. | Experience designer |
| System recovers from BLE disconnects in under 5 seconds without manual intervention. | Chaos test log demonstrating automatic reconnection after forced disconnect. | Platform reliability engineer |
| Operators can override cube-derived scenes during live shows. | Control UI audit verifying override button availability and event logs. | Show operator |

## Phases and checklists

### Discovery

- [ ] Inventory cube BLE services and characteristics via vendor docs and protocol sniffing.
- [ ] Capture baseline telemetry stream (orientation quaternions, move notations, battery events) into structured logs.
- [ ] Validate Bluetooth stack compatibility with Linux SBC and macOS development hosts.
- [ ] Document cube firmware limits: update frequency, MTU, notification rate caps.
- [ ] Align with experience design team on target scenes and cube gestures to prioritise.

### Signal capture implementation

- [ ] Build a dedicated `CubeTelemetryClient` atop `bleak` with connection retry and characteristic subscription APIs.
- [ ] Normalize cube state updates into a canonical event schema (`CubeStateEvent`) including orientation, move history, and confidence scores.
- [ ] Store rolling state in Redis or in-memory cache for downstream consumers with expiry semantics.
- [ ] Emit events onto the internal event bus (`src/eventing/bus.py`) with topic versioning and tracing metadata.
- [ ] Instrument metrics for latency, disconnect frequency, and packet loss using OpenTelemetry exporters.

### Scene mapping engine

- [ ] Define declarative mapping DSL (`docs/specs/cube_scene_rules.md`) covering orientation ranges, solved-state detection, and move sequences.
- [ ] Implement rule parser that compiles DSL into evaluation graph executed in the scene service (`src/scenes/engine.py`).
- [ ] Add simulation harness reading recorded cube traces and producing scene IDs for offline validation.
- [ ] Integrate override controls into show operator UI (`src/ui/control_panel/overrides.tsx`) with audit logging hooks.
- [ ] Configure fallback scene pipeline to revert to default cues when cube signal is stale beyond 2 seconds.

### Validation and rollout

- [ ] Run latency benchmarks comparing lab BLE captures to on-stage RF environment.
- [ ] Execute end-to-end dress rehearsal with designers to validate choreography timing.
- [ ] Finalise runbook documenting recovery steps, override workflows, and telemetry dashboards.
- [ ] Pilot in one live event with feature flag gating scene mapping service.
- [ ] Gather post-event metrics and qualitative feedback, iterate on rule tuning.

## Narrative walkthrough

Discovery centres on understanding the cube's BLE interface and environmental constraints. By logging raw characteristic notifications early, we derisk integration by grounding design decisions in actual signal quality rather than assumptions from marketing sheets. We simultaneously surface dependencies with networking and firmware teams so that any MTU or notification rate changes have owners.

Signal capture begins once we trust the protocol surface. Implementing a `CubeTelemetryClient` on top of `bleak` keeps parity across Linux and macOS operators, while the canonical `CubeStateEvent` schema ensures downstream services receive consistent payloads. Metrics and tracing instrumentation are emphasised so we can monitor packet loss and latency regressions in rehearsal spaces and during live shows.

The scene mapping engine translates telemetry into actionable cues. A declarative DSL keeps creative stakeholders in the loop, allowing them to express patterns (e.g., "if cube is solved while facing front, trigger Finale Scene") without deep programming knowledge. Compiling these rules into an evaluation graph ensures runtime efficiency. The simulation harness gives designers immediate feedback on rule behaviour before risking live audiences.

Validation runs in parallel with user experience milestones. Dress rehearsals and pilot deployments surface real-world RF noise, operator preferences, and failure modes (like the cube leaving range). The runbook and dashboards close the loop, helping operators interpret system state and take corrective action without engineering presence.

## Data flow diagram

```
[Bluetooth Cube]
      |
      v
[CubeTelemetryClient] --(metrics)--> [Observability Stack]
      |
      v
[Event Bus: cube.state]
      |
      v
[Scene Rule Evaluator] --(override channel)--> [Operator UI]
      |
      v
[Lighting/Media Controller]
```

## Risk analysis

| Risk | Probability | Impact | Mitigation strategy | Early warning signals |
| --- | --- | --- | --- | --- |
| BLE signal attenuation on stage | Medium | High | Deploy antenna extenders, pre-stage RF scans, provide wired fallback controller. | Rising latency metrics, packet loss alerts, stage crew reporting dropouts. |
| Cube firmware throttles notifications under heavy motion | Medium | Medium | Coordinate with vendor for firmware update, implement adaptive sampling and interpolation. | Telemetry frequency dips during rehearsal move bursts. |
| Mapping DSL misconfigures scenes | Low | High | Enforce schema validation, add sandbox preview with approval workflow. | Simulation harness discrepancies, override usage spikes. |
| Operator override conflicts with automated cues | Low | Medium | Build locking semantics where manual overrides pause automation for fixed window. | Concurrent override + automation logs, operator feedback. |

### Mitigation checklist

- [ ] Schedule RF site survey two weeks before premiere.
- [ ] Prototype wired controller fallback and document switch-over protocol.
- [ ] Create automated regression tests for top 20 mapping rules using recorded cube traces.
- [ ] Add alerting rules for sustained override usage beyond 3 minutes.

## Outcome snapshot

Once shipped, cube twists register within sub-150 ms latency budgets and deterministically trigger scenes defined by experience designers. Operators retain full control via overrides and can rely on dashboards that visualise cube connectivity and rule execution. The system unlocks choreographed audience participation segments, providing telemetry archives for iterative rule tuning while maintaining resilience against RF interruptions.
