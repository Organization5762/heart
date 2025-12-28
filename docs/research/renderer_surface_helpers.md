# Renderer surface helper extraction

## Summary

The render pipeline now delegates renderer surface caching and surface merge policy
to dedicated helpers. The goal is to keep `RenderPipeline` focused on orchestration
while reusing the same caching and merge behavior across render variants.

## Implementation notes

- `RendererSurfaceCache` (`src/heart/runtime/rendering/surface_cache.py`) owns the
  cache keyed by renderer identity, display mode, and output size. It returns
  cleared surfaces on reuse and respects `Configuration.render_screen_cache_enabled()`.
- `SurfaceMerger` (`src/heart/runtime/rendering/surface_merge.py`) centralizes
  the merge strategies, reusing `SurfaceComposer` for batched paths and handling
  in-place or parallel merges based on `RenderMergeStrategy`.
- `RenderPipeline` (`src/heart/runtime/render/pipeline.py`) now composes these
  helpers instead of managing cache or merge logic inline.

## Materials

- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/rendering/surface_cache.py`
- `src/heart/runtime/rendering/surface_merge.py`
- `src/heart/runtime/rendering/composition.py`
