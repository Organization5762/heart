# Input Event Bus & State Store Plan

## Background

The current input pathway drains the global pygame queue inside `GameLoop` and has
peripherals mutating their own state. To support reactive listeners and simple state
queries, we need a project-local event bus paired with a shared state store.

## Goals

- Normalize how peripherals publish input and requests.
- Let systems subscribe to events with lightweight callbacks or decorators.
- Provide a `State.get()`-style API for the latest input snapshots.
- Incrementally adopt the bus without breaking existing device integrations.

## Incremental Checklist

1. [x] Land an `EventBus` core module with subscribe/emit/unsubscribe helpers and unit tests
   covering subscriber ordering, decorator registration, and failure isolation.
1. [x] Thread the event bus through the `GameLoop`, bridging pygame/system events to
   subscribers while maintaining current behavior.
1. [ ] Introduce a shared `StateStore` that the bus can update on every emission,
   exposing `State.get()` helpers for consumers.
1. [ ] Migrate representative peripherals (switch, bluetooth switch, gamepad) to emit
   structured events via the bus instead of mutating device-level state.
1. [ ] Update high-level consumers (navigation, modes) to read from the state store and
   add regression tests demonstrating multi-device arbitration.

## Notes

- Keep the bus synchronous for now; if latency becomes an issue we can explore
  background dispatchers.
- Focus early tests on pure Python logic so they remain deterministic in CI.

## Architecture Overview

The first iteration keeps the event bus and state store in-process alongside the
`GameLoop`. The loop will hydrate a singleton `InputEventBus` on start-up and
pass it to peripherals during initialization. Peripherals emit domain events to
the bus, which immediately notifies registered subscribers and writes the latest
payload into the `StateStore`.

```
pygame -> GameLoop -> InputEventBus.emit() -> subscribers
                                   \-> StateStore.update()
```

- `GameLoop` remains the orchestrator that polls pygame and exposes lifecycle
  hooks for peripherals.
- `InputEventBus` exposes `subscribe`, `unsubscribe`, `emit`, and
  `subscription` decorator helpers.
- `StateStore` provides `get(path, default=None)` and `snapshot()` accessors.
- Peripherals focus on translating hardware state to typed events without
  retaining global mutable state.

## Event Model & Schema

Each event is a dataclass or `TypedDict` containing:

1. `type`: validated event label (see naming conventions below).
1. `producer_id`: stable identifier for the component that emitted the event.
1. `timestamp`: `datetime` in UTC; the emitter is responsible for populating it.
1. `payload`: arbitrary structured data (e.g., `{"port": 1, "pressed": True}`).

Guidelines:

- Keep payloads JSON-serializable to enable future persistence/telemetry.
- Standardize common fields (`device_id`, `user_id`, `strength`) so consumers
  can merge multiple devices.

### Naming Conventions

- `producer_id` must be a lowercase slug containing `[a-z0-9]` and dashes,
  e.g., `gamepad-1`, `bluetooth-switch`, or `system-ui`. Each logical producer
  (hardware device, virtual adapter, macro) owns exactly one ID for the lifetime
  of the process.
- Event `type` strings follow `<domain>.<verb>` and may optionally include a
  qualifier segment (`<domain>.<qualifier>.<verb>`). Domains and qualifiers use
  lowercase slug syntax identical to `producer_id`. Verbs use imperative form
  (`pressed`, `moved`, `updated`). Examples: `switch.pressed`,
  `cursor.delta.moved`, `navigation.mode.updated`.
- The combination of `producer_id` + `type` must be unique per emission cycle;
  downstream consumers rely on this tuple to key state snapshots.

### Helper Types

Add `InputEvent` protocol in `src/heart/events/types.py` to capture the shape
above and enable static typing in subscribers. The protocol should surface a
`producer_id: str` property and helper validation for the naming rules.

## State Store Semantics

- The store tracks the latest event per `(producer_id, type)` tuple and exposes
  aggregation helpers for consumers dealing with multi-device input.
- `StateStore.update(event)` stores the payload and timestamp under a composite
  key and applies the configured aggregation contract (see below). Provide
  helpers:
  - `StateStore.get_latest(type, producer_id=None)`
  - `StateStore.get_all(type, aggregation="default")`
- Expose a read-only `StateSnapshot` mapping for consumers who need bulk state
  without mutating rights.
- The bus is responsible for invoking `StateStore.update()` before dispatching
  subscribers so synchronous consumers always observe the latest state.

## Migration Strategy

1. Introduce a thin compatibility layer inside each peripheral that wraps the
   existing imperative code and emits equivalent events. Maintain the old code
   path until downstream consumers migrate.
1. Add toggleable feature flags (e.g., `ENABLE_INPUT_EVENT_BUS`) to allow staged
   rollout and quick rollback.
1. Update mode/navigation controllers to read from `StateStore` while leaving
   their public API unchanged.
1. Remove deprecated peripheral state mutations once confidence is gained.

## Testing Approach

- Unit test `InputEventBus` for ordering guarantees, subscriber isolation, and
  decorator ergonomics.
- Add integration tests in `tests/integration/input/` that simulate pygame
  events, drive the bus through the game loop, and assert that both the state
  store and subscribers see expected results.
- Include regression tests around multi-device arbitration to confirm that the
  state store resolves conflicts deterministically, including different
  aggregation modes for the same event type.

### Aggregation Contracts

Multiple producers emitting the same event type must explicitly declare how
their signals combine. Document the contract in a registry colocated with the
bus:

- `overwrite` (default): the latest payload replaces prior values for the
  `(producer_id, type)` tuple and `StateStore.get_all()` returns a mapping of all
  producers.
- `sum`: numeric payload fields are summed across producers to produce a single
  composite view.
- `difference`: the newest payload is subtracted from the accumulated baseline,
  useful for drift-correction devices.
- `sequence`: payloads are appended to a per-type list to expose an ordered set
  of simultaneous options.
- Custom aggregators may be registered when domain-specific logic is needed;
  they must accept the previous aggregate and the new event, and return the
  updated aggregate plus the per-producer snapshot.

Producers select an aggregation mode when registering with the bus. The bus
persists per-producer snapshots regardless of aggregation so downstream actors
can inspect individual contributions even when a composite aggregate is in use.

### Producer Lifecycle & Disconnect Semantics

Explicit producer registration is mandatory so the bus can associate a
`producer_id` with its supported event types, aggregation contract, and optional
disconnect policy. Registration returns a handle the producer must retain to
refresh liveness. The lifecycle flows below illustrate how disconnects interact
with the state store and subscribers:

1. **First-time USB switch plug-in.**

   - Device enumerator discovers a new HID peripheral and invokes
     `InputEventBus.register_producer()` with `producer_id="usb-switch-1"`, the
     supported event types (`switch.pressed`, `switch.released`), and an
     `overwrite` aggregation contract.
   - The bus records the producer metadata and seeds an initial state entry with
     `status="available"` under the reserved event `system.lifecycle.connected`.
   - Downstream consumers subscribed to lifecycle events initialize their own
     bookkeeping (e.g., presenting the switch as an option in configuration
     UIs).
   - The device begins emitting `switch.*` events as normal.

1. **Transient disconnect with automatic recovery.**

   - Heartbeat threads associated with the producer periodically call
     `producer_handle.touch()`; if the bus misses `N` consecutive touches, it
     emits a synthetic `system.lifecycle.suspected_disconnect` event for that
     `producer_id` and updates the state snapshot to
     `{"status": "suspected_disconnect", "missed_heartbeats": N}`.
   - Consumers may choose to soft-disable the device or prompt the user while
     continuing to hold historical snapshots in case the device returns quickly.
   - When the hardware rejoins and the heartbeat resumes, the producer reuses
     its original ID to call `touch()`; the bus emits
     `system.lifecycle.recovered`, promoting the state back to
     `status="available"` and preserving prior aggregation state so the device
     can seamlessly resume.

1. **Explicit producer shutdown.**

   - Software-backed producers (e.g., virtual remotes or cloud relays) should
     call `producer_handle.disconnect(reason=...)` during teardown.
   - The bus immediately emits `system.lifecycle.disconnected` with the supplied
     reason and prunes active aggregation state for that producer. The historical
     snapshot remains accessible via audit helpers for debugging.
   - Consumers can confidently remove UI affordances or reassign bindings,
     knowing that no further events will arrive for the `(producer_id, type)`
     tuples associated with the disconnected producer.

1. **Replacement hardware using a recycled port.**

   - When a new physical device occupies the same port, the enumerator must
     generate a fresh `producer_id` (e.g., `usb-switch-2`) to avoid conflating
     historical events with the newcomer.
   - Registration of the replacement automatically archives the old producer and
     emits `system.lifecycle.replaced`, allowing consumers to migrate
     configuration or solicit confirmation from the user.

These flows keep `producer_id` stable across transient failures but force new
IDs for genuinely different devices. Lifecycle events are ordinary bus events,
so downstream actors can subscribe to `system.lifecycle.*` to drive UX, cleanup,
or logging.

## Open Questions

- Do we need backpressure or batching for high-frequency devices (e.g., analog
  joysticks)? For now, the plan assumes no.
- Should we persist event history for debugging? Consider adding optional
  ring-buffer support to `StateStore` if visibility becomes an issue.
- How do remote inputs (cloud, web) plug into the bus? Define adapters once the
  local pathway stabilizes.
