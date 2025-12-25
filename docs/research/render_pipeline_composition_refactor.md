# Render pipeline composition refactor

## Summary

Clarify render pipeline responsibilities by delegating per-renderer frame work to
`RendererProcessor` while keeping `RenderPipeline` focused on dispatch, merge
strategy selection, and surface composition.

## Motivation

`RenderPipeline` currently coordinates execution strategy, merge policy, surface
composition, and per-renderer frame handling. The per-renderer work (surface
preparation, renderer initialization, `_internal_process` execution, and timing
metrics) is easier to reason about when isolated behind a dedicated processor.
That separation keeps the pipeline focused on orchestration and reduces the
number of cross-cutting concerns in a single module.

## Implementation notes

- Rename the frame processor to `RendererProcessor` to make its scope explicit.
- Update `RenderPipeline` to delegate renderer execution and queue depth updates
  to `RendererProcessor` while retaining merge/composition behavior.
- Keep timing snapshots centralized by sharing the processor timing tracker with
  the pipeline.

## Materials

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/renderer_processor.py`
- `src/heart/runtime/rendering/surface_provider.py`
- `src/heart/runtime/rendering/timing.py`
