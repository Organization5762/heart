# Input Event Bus & State Store Plan

## Problem Statement

Replace the ad-hoc peripheral state mutations in the game loop with a structured event bus and shared state store so systems can subscribe to input changes and read deterministic snapshots.

## Materials

- Existing `GameLoop` implementation and peripheral modules under `src/heart/peripheral`.
- Proposed bus implementation in `src/heart/events`.
- Access to hardware peripherals (switches, Bluetooth controllers, gamepads) for validation.
- Test harness capable of simulating pygame events.

## Opening Abstract

Today, peripherals mutate module-level state and the `GameLoop` drains pygame events directly. This makes it difficult to trace state changes, support multiple devices, or replay inputs. The goal is to introduce an in-process event bus coupled with a state store. Peripherals publish typed events, subscribers react synchronously, and consumers query the latest snapshots through a simple API. The migration must maintain backwards compatibility while we transition each device.

### Why Now

Upcoming multi-device installations require deterministic arbitration between inputs, and the MQTT split plan depends on structured events. Establishing the bus now simplifies both efforts.

## Success Criteria

| Behaviour | Signal | Owner |
| --- | --- | --- |
| Event bus delivers typed payloads for core peripherals | Unit tests show `switch.pressed` and `gamepad.moved` events emitted with timestamps | Peripheral lead |
| State store exposes latest snapshots with aggregation | `StateStore.get_latest()` returns coherent values during integration tests | Runtime engineer |
| Migration preserves existing scene behaviour | Regression suite passes with bus enabled and legacy code removed | QA owner |

## Task Breakdown Checklists

### Discovery

- [ ] Document current peripheral state mutations and identify consumers.
- [ ] Define canonical event types, producer IDs, and payload schemas.
- [ ] Assess lifecycle requirements (connect, disconnect, heartbeat).

### Implementation – Core Infrastructure

- [ ] Implement `InputEventBus` with `subscribe`, `unsubscribe`, decorator support, and synchronous dispatch.
- [ ] Introduce `StateStore` with aggregation strategies (`overwrite`, `sum`, `sequence`).
- [ ] Provide helper types (`InputEvent` protocol) enforcing naming conventions.

### Implementation – Peripheral Migration

- [ ] Wrap switch, Bluetooth switch, and gamepad integrations to emit events while preserving existing behaviour.
- [ ] Register producers with lifecycle hooks (connected, suspected_disconnect, recovered, disconnected).
- [ ] Add feature flag (`ENABLE_INPUT_EVENT_BUS`) for staged rollout.

### Validation

- [ ] Build integration tests simulating pygame events and asserting bus emissions plus state updates.
- [ ] Exercise multi-device arbitration scenarios to verify aggregation policies.
- [ ] Capture logs demonstrating lifecycle events during hardware connect/disconnect.

## Narrative Walkthrough

Discovery clarifies which modules mutate shared state and what schemas are required. Core infrastructure delivers the event bus, state store, and naming enforcement so all publishers and subscribers share expectations. Peripheral migration then adapts representative devices to the new system, ensuring lifecycle hooks and feature flags allow incremental rollout. Validation closes by simulating complex scenarios and confirming scenes behave identically while benefiting from structured state access.

## Visual Reference

| Flow Stage | Description | Artifact |
| --- | --- | --- |
| Pygame event intake | `GameLoop` drains events and emits typed bus events | `InputEventBus.emit()` |
| State update | `StateStore.update()` records latest payload and aggregate | `StateStore` snapshot |
| Subscriber reaction | Systems consume events synchronously | Navigation controllers, mode handlers |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning |
| --- | --- | --- | --- | --- |
| Synchronous bus introduces latency spikes | Medium | Medium | Keep handlers lightweight, consider background dispatch for heavy consumers | Frame timing logs show increased jitter |
| Aggregation rules fail for edge cases | Medium | High | Document policies, add regression tests per event type | Snapshot diffs show inconsistent values |
| Feature flag rollback incomplete | Low | High | Maintain legacy path until regression suite passes without it | Legacy toggle required after rollout |

### Mitigation Tasks

- [ ] Profile dispatch time and identify handlers requiring async offloading.
- [ ] Create aggregation registry with test fixtures per mode.
- [ ] Automate feature-flag toggles in CI to ensure both paths execute.

## Outcome Snapshot

Peripherals publish structured events through a shared bus, the state store exposes deterministic snapshots, and scenes rely on the new API without manual state plumbing. Lifecycle events help operators reason about device availability, and the system is ready for remote input pipelines.
