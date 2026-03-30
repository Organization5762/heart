# Renderer surface helper collapse

## Summary

The render pipeline no longer routes simple surface collection and pairwise
merging through dedicated wrapper classes. Those helpers only had one caller,
so the logic now lives directly in `RenderPipeline` while `SurfaceComposer`
remains available for the batched merge path.

## Implementation notes

- `RenderPipeline` (`src/heart/runtime/rendering/pipeline.py`) now decides
  directly whether renderer execution should stay serial or go through the
  shared executor.
- The pipeline now owns in-place surface merging, including the pairwise merge
  path used for the binary render variant.
- `SurfaceComposer` (`src/heart/runtime/rendering/composition.py`) is still
  used when the configured merge strategy selects the batched path.

## Materials

- `src/heart/runtime/rendering/pipeline.py`
- `src/heart/runtime/rendering/composition.py`
- `src/heart/runtime/rendering/renderer_processor.py`
