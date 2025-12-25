# Renderer base-class layout

## Overview

Renderer base classes are split into dedicated modules to keep responsibilities clear while
keeping public imports centralized in `heart.renderers`.

## Layout

- `src/heart/renderers/base.py` defines `BaseRenderer` for renderers without managed state.
- `src/heart/renderers/atomic.py` defines `AtomicBaseRenderer`, which manages immutable
  state snapshots and shared rendering utilities.
- `src/heart/renderers/stateful.py` defines `StatefulBaseRenderer`, which extends
  `AtomicBaseRenderer` to subscribe to observable state providers.
- `src/heart/renderers/__init__.py` re-exports these base classes so call sites can import
  from `heart.renderers` without tracking the module split.

## Materials

- `src/heart/renderers/base.py`
- `src/heart/renderers/atomic.py`
- `src/heart/renderers/stateful.py`
- `src/heart/renderers/__init__.py`
