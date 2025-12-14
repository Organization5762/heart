# Renderer refactor notes

## Overview

- Split the Pacman ghost renderer into dedicated provider, state, and renderer modules under `src/heart/display/renderers/pacman/`.
- Moved the ThreeDGlasses renderer into the same three-file structure at `src/heart/display/renderers/three_d_glasses/`.
- Both refactors keep rendering responsibilities in the renderer classes while providers advance immutable state snapshots.

## Implications

- Configuration modules can continue importing `PacmanGhostRenderer` and `ThreeDGlassesRenderer` from `heart.display.renderers.*` because `__init__.py` shims were added.
- Providers now encapsulate spawn/animation timing logic, which simplifies renderer initialization and keeps update code reusable.
- Asset loading for Pacman sprites is gated by an asset version counter to avoid unnecessary reloads between frames.
