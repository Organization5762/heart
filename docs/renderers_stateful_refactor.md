# Renderer state refactors for cloth sail and multicolor

## Overview

The cloth sail and multicolor renderers now follow the provider/state/renderer split used by other stateful effects. Each renderer consumes a dedicated provider that emits immutable state snapshots driven by the shared game tick and clock stream.

## Implementation notes

- `heart.display.renderers.cloth_sail` now stores shader timing inside `ClothSailState`, advanced by `ClothSailStateProvider` using the main clock cadence. The renderer reads `elapsed_seconds` instead of tracking `perf_counter` internally.
- `heart.display.renderers.multicolor` keeps the procedural color math in the renderer while the `MulticolorStateProvider` handles elapsed-time accumulation. The renderer uses the provided `elapsed_seconds` to generate frames.
- Program configurations instantiate renderers with their matching providers so the state streams come from the shared `PeripheralManager` observables.

## Files touched

- `src/heart/display/renderers/cloth_sail/` now contains `provider.py`, `renderer.py`, and `state.py` to isolate timing state from OpenGL drawing code.
- `src/heart/display/renderers/multicolor/` mirrors the same structure for the multicolor effect.
- `src/heart/programs/configurations/cloth_sail.py` and `src/heart/programs/configurations/lib_2025.py` construct the new providers before wiring renderers into modes.
