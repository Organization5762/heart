______________________________________________________________________

## title: Renderer/Provider/State Separation Touchpoints

## Summary

This note tracks renderer refactors that move state mutation into provider helpers so
renderers focus on converting state to pixels while providers own state updates.

## Observations

- The pixel rain/slinky renderers updated their own state each frame even though a
  dedicated provider already existed for those effects.
- The Yo Listen renderer owned flicker and scroll state updates, which made the
  renderer responsible for both animation logic and drawing.
- Spritesheet random loop timing lived in the renderer instead of the provider.
- Sliding image renderers were mutating their state despite using tick-driven
  observables.

## Implementation Notes

- `src/heart/renderers/pixels/provider.py` now supplies `next_state` helpers for
  rain and slinky, plus a `update_color` helper for border color changes.
- `src/heart/renderers/spritesheet_random/provider.py` owns duration scaling,
  switch-state updates, and frame/clock-driven state progression.
- `src/heart/renderers/yolisten/provider.py` now handles flicker, scroll
  calibration, scroll scaling, and word-position updates.
- `src/heart/renderers/sliding_image/provider.py` offers reset helpers so the
  renderers avoid direct state mutation.

## Materials

- `src/heart/renderers/pixels/renderer.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/spritesheet_random/renderer.py`
- `src/heart/renderers/spritesheet_random/provider.py`
- `src/heart/renderers/yolisten/renderer.py`
- `src/heart/renderers/yolisten/provider.py`
- `src/heart/renderers/sliding_image/renderer.py`
- `src/heart/renderers/sliding_image/provider.py`
