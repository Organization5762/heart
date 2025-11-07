# Input Event Bus Developer Guide

## Overview

The input event bus is a synchronous in-process dispatcher for peripheral input.
Peripherals normalise raw payloads into `heart.peripheral.core.Input` objects and
emit them through `EventBus.emit()`. Subscribers receive events immediately and
the shared `StateStore` captures the latest value for each `(event_type, producer_id)` pair.

## Publishing events

1. Inject or request an `EventBus` instance. `GameLoop` exposes the bus via
   `GameLoop.event_bus` and propagates it to detected peripherals when
   `ENABLE_INPUT_EVENT_BUS` is enabled.
1. Compose payloads with the helpers in `heart.events.types`. For example,
   `AccelerometerVector(x, y, z).to_input(producer_id=...)` yields a typed input.
1. Call `event_bus.emit(input_event)` inside the peripheral once the payload is
   validated. Exceptions raised by subscribers are logged and do not block
   other handlers.

### Lifecycle signalling

Peripherals should emit lifecycle transitions so downstream systems can reason
about availability. Use `HeartRateLifecycle`, `SwitchButton.long_press`, and
similar helpers to encode `connected`, `suspected_disconnect`, `recovered`, and
`disconnected` states. Maintain an internal status cache to avoid publishing
unchanged lifecycle events.

## Reading state snapshots

`EventBus.state_store` tracks the most recent event per producer. Call
`StateStore.get_latest(event_type, producer_id)` to read a single entry or
`StateStore.snapshot()` to clone the entire store for deterministic inspection.
`GameLoop.latest_input()` and `GameLoop.input_snapshot()` wrap these calls for
renderers and controllers.

## Testing

- Use the concrete `EventBus` in unit tests and subscribe to the event types
  under test to assert emitted payloads.
- The helpers in `heart.events.types` return full `Input` instances, enabling
  direct comparison in tests without constructing dictionaries manually.
- `StateStore` objects are safe to share across threads; snapshots return
  read-only `MappingProxyType` views so tests can verify immutability.
