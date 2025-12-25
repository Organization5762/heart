# Research note: renderer base-class split

## Context

Renderer base classes are referenced widely throughout the runtime and navigation layers. The
split into base, atomic, and stateful modules keeps each responsibility isolated while retaining
stable import paths through `heart.renderers`.

## Notes

- `BaseRenderer` remains the entry point for renderers that do not track state internally.
- `AtomicBaseRenderer` keeps state snapshot utilities and timing instrumentation in a focused
  module.
- `StatefulBaseRenderer` owns observable subscription handling for renderer state updates.

## Sources

- `src/heart/renderers/base.py`
- `src/heart/renderers/atomic.py`
- `src/heart/renderers/stateful.py`
- `src/heart/renderers/__init__.py`

## Materials

- `src/heart/renderers/base.py`
- `src/heart/renderers/atomic.py`
- `src/heart/renderers/stateful.py`
- `src/heart/renderers/__init__.py`
