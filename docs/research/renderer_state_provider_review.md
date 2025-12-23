# Renderer state/provider boundary review

## Summary

- Shifted the pixel-family renderers (Border, Rain, Slinky) so providers emit
  immutable state updates from the game-tick stream, while renderers only draw
  based on the current state snapshot.
- Updated the Pacman ghost renderer to receive state updates from its provider
  instead of mutating state during rendering.

## Findings

- `RainStateProvider` and `SlinkyStateProvider` now own the per-tick updates via
  `PeripheralManager.game_tick`, keeping animation progression inside the
  provider layer.
- `BorderStateProvider` owns color changes through a subject so renderer color
  updates remain a state update rather than a renderer mutation.
- `PacmanGhostStateProvider` now advances positions and sprite variants through
  the tick stream, and the renderer only swaps cached sprites when the state
  indicates an asset change.

## Materials

- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/pixels/renderer.py`
- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pacman/renderer.py`
