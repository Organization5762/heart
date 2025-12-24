# Render pipeline refactor note

## Summary

The render-loop composition and surface-merging logic now lives in a dedicated
`RenderPipeline` helper so `GameLoop` can focus on initialization, event handling,
and device updates. The pipeline retains the renderer scheduling, surface caching,
and render-variant selection behaviors previously embedded in the loop.

## Sources

- `src/heart/runtime/render_pipeline.py` (new render pipeline helper)
- `src/heart/runtime/game_loop.py` (game loop orchestration)
- `src/heart/loop.py` (renderer variant selection)
- `src/heart/environment.py` (legacy import shim updates)

## Materials

- None
