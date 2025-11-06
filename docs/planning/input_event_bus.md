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

1. `type`: namespaced event label (`"switch/pressed"`).
1. `timestamp`: `datetime` in UTC; the emitter is responsible for populating it.
1. `payload`: arbitrary structured data (e.g., `{"port": 1, "pressed": True}`).

Guidelines:

- Prefer namespaced event types (`<device>/<action>`) to avoid collisions.
- Keep payloads JSON-serializable to enable future persistence/telemetry.
- Standardize common fields (`device_id`, `user_id`, `strength`) so consumers
  can merge multiple devices.

### Helper Types

Add `InputEvent` protocol in `src/heart/events/types.py` to capture the shape
above and enable static typing in subscribers.

## State Store Semantics

- The store tracks the latest event per `type` and optionally per `device_id`.
- `StateStore.update(event)` stores the payload and timestamp under a composite
  key. Provide helpers:
  - `StateStore.get_latest(type, device_id=None)`
  - `StateStore.get_all(type)`
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
  state store resolves conflicts deterministically.

## Open Questions

- Do we need backpressure or batching for high-frequency devices (e.g., analog
  joysticks)? For now, the plan assumes no.
- Should we persist event history for debugging? Consider adding optional
  ring-buffer support to `StateStore` if visibility becomes an issue.
- How do remote inputs (cloud, web) plug into the bus? Define adapters once the
  local pathway stabilizes.
