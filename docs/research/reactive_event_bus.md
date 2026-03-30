# Reactive input stream scheduling and sharing

## Problem

Peripheral event streams are cold observables by default. When multiple subscribers attach to the
same peripheral or to a shared controller/view stream, each subscriber can trigger a new
subscription to the underlying source unless the stream is shared. That repeats work in input
polling intervals and makes it harder to reason about performance when more observers are added.

## Update

- The peripheral `observe` stream now shares a single subscription, so multiple subscribers reuse
  the same underlying event source.
- Shared controller and profile streams also use shared subscriptions so multiple consumers can
  reuse the same keyboard, gamepad, and logical mapping pipelines.

## Materials

- `HEART_RX_EVENT_BUS_SCHEDULER` (`inline`, `background`, `input`) for legacy event-stream
  scheduling configuration that still applies to shared Rx helpers.

## References

- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/utilities/env.py`
