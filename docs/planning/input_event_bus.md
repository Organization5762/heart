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
1. [ ] Thread the event bus through the `GameLoop`, bridging pygame/system events to
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
