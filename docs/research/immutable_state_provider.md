# Immutable state providers for stateful renderers

## Problem statement

Some renderers only emit a single immutable state snapshot, but they used
renderer-specific provider classes to do so. This refactor introduces a
generic immutable provider and wires it into the stateful base so static
state can be expressed without bespoke provider scaffolding.

## Implementation notes

- `ImmutableStateProvider` in `src/heart/renderers/state_provider.py` emits a
  single shared state snapshot.
- `StatefulBaseRenderer` now accepts a static `state=` argument and wraps it
  in the immutable provider when no builder is supplied.
- `RenderColor` uses the generic immutable provider when constructed with a
  fixed color.
- `FractalScene` creates its runtime during initialization and sets an
  immutable provider for the resulting state.

## Sources

- `src/heart/renderers/state_provider.py`
- `src/heart/renderers/__init__.py`
- `src/heart/renderers/color/renderer.py`
- `src/heart/renderers/three_fractal/renderer.py`

## Materials

- None.
