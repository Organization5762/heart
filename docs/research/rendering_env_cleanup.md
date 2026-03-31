# Rendering Env Cleanup

## Problem

`heart.utilities.env.rendering` still exposed many knobs from removed render
pipeline experiments even though the live runtime only used two of them. That
made the configuration surface harder to trust and left orphaned helper code in
the tree.

## Outcome

- Kept only the active runtime composition knobs:
  `HEART_RENDER_CRASH_ON_ERROR` and `HEART_RENDER_TILE_STRATEGY`.
- Removed unused render-plan, merge, parallelism, timing, and cache settings.
- Deleted the orphaned `RendererTimingTracker` helper after removing its enum
  dependencies.

## Source Files

- `src/heart/utilities/env/rendering.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/navigation/composed_renderer.py`
