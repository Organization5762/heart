# Pixels and spritesheet renderer refactors

- **Scope:** move legacy single-file renderers into provider/state/renderer packages.
- **Renderers:**
  - Pixels family (Border, Rain, Slinky) now live under `src/heart/display/renderers/pixels/` with `provider.py`, `state.py`, and `renderer.py`.
  - SpritesheetLoop now loads from `src/heart/display/renderers/spritesheet/`.
  - SpritesheetLoopRandom now loads from `src/heart/display/renderers/spritesheet_random/`.

## Notes

- Providers own initial state creation and per-frame updates, keeping renderers draw-only.
- Configuration modules importing from `heart.display.renderers.pixels` and the two spritesheet paths remain valid after the move.
