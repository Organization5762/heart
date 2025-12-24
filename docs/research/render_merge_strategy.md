# Render merge strategy tuning

## Technical problem

The render loop merges multiple renderer surfaces into a single frame. The
previous approach merged each surface with an individual `blit` call, which adds
Python overhead when multiple renderer layers are active.

## Notes

- `heart.environment.GameLoop._render_surface_iterative` now batches merges into
  a single `Surface.blits` call when `HEART_RENDER_MERGE_STRATEGY=blits` to reduce
  per-surface overhead in multi-renderer scenes.
- The environment switch is surfaced through
  `heart.utilities.env.Configuration.render_merge_strategy` so operators can
  revert to the `loop` merge path if needed.

## Materials

- `src/heart/environment.py`
- `src/heart/utilities/env.py`
