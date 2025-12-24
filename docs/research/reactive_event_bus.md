# Reactive event bus scheduling and sharing

## Problem

Peripheral event streams are cold observables by default. When multiple subscribers attach to the
same peripheral or to the merged event bus, each subscriber can trigger a new subscription to the
underlying stream. That repeats work in input polling intervals and makes it harder to reason
about performance when more observers are added.

## Update

- The peripheral `observe` stream now shares a single subscription, so multiple subscribers reuse
  the same underlying event source.
- The peripheral manager event bus now handles an empty peripheral list safely and can move event
  delivery onto a configured scheduler.

## Materials

- `HEART_RX_EVENT_BUS_SCHEDULER` (`inline`, `background`, `input`)

## References

- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/utilities/env.py`
