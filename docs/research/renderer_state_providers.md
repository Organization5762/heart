# Renderer state providers for fixed snapshots

## Problem statement

Several renderers need a single immutable state snapshot (for example, a fixed
color) and currently rely on bespoke provider classes to emit that snapshot. The
boilerplate makes it harder to keep renderer configuration consistent with the
shared state model and complicates initialization paths.

## Notes

- Added a generic `FixedStateProvider` to emit a single state snapshot via the
  existing observable interface. This keeps fixed configuration in state while
  sharing the provider plumbing. See `src/heart/peripheral/core/providers/__init__.py`.
- Updated `StatefulBaseRenderer` to accept either a streaming builder or a fixed
  state snapshot so warm-up and subscriptions share the same lifecycle path. See
  `src/heart/renderers/__init__.py`.
- Simplified `RenderColorStateProvider` to build on the new fixed-state provider
  and allowed `RenderColor` to accept a state snapshot directly. See
  `src/heart/renderers/color/provider.py` and
  `src/heart/renderers/color/renderer.py`.

## Materials

- Source files:
  - `src/heart/peripheral/core/providers/__init__.py`
  - `src/heart/renderers/__init__.py`
  - `src/heart/renderers/color/provider.py`
  - `src/heart/renderers/color/renderer.py`
