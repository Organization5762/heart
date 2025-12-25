# Render pipeline frame processor refactor

## Summary

Refactor per-renderer frame preparation, execution, and logging into a dedicated
`RendererFrameProcessor`. The goal is to keep `RenderPipeline` focused on
render dispatch, executor management, and surface composition while preserving
existing timing and logging behavior.

## Motivation

`RenderPipeline` previously mixed composition orchestration with low-level
renderer frame handling and logging. Splitting the frame processing logic into a
separate module reduces the number of concerns inside the pipeline and makes it
simpler to evolve per-renderer behavior without touching dispatch logic.

## Implementation notes

- Added `RendererFrameProcessor` to encapsulate surface preparation, renderer
  initialization, per-frame execution, timing updates, and per-renderer logging.
- Updated `RenderPipeline` to delegate per-renderer work and queue depth updates
  to the new processor while keeping merge strategy selection and composition
  behavior intact.
- Preserved timing snapshots by sharing the same `RendererTimingTracker`
  instance between the processor and the pipeline.

## Materials

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/renderer_processor.py`
- `src/heart/runtime/rendering/timing.py`
