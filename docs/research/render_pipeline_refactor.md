# Render pipeline refactor notes

## Summary

- The render pipeline previously managed per-renderer setup, frame timing, and
  logging alongside orchestration and surface composition.
- Per-renderer processing now lives in a focused helper so the pipeline can
  stay centered on scheduling and composition flow.

## Technical motivation

The `RenderPipeline` class handled both orchestration (queue depth decisions,
surface collection, and composition) and renderer-specific concerns (clock
validation, renderer initialization, and metrics logging). Splitting the
renderer-specific work into its own helper clarifies responsibilities and keeps
each file focused on one concern.

## Implementation notes

- Added `RendererFrameProcessor` to encapsulate renderer surface preparation,
  frame execution, and metrics logging.
- Updated `RenderPipeline` to delegate renderer work to the new processor while
  keeping dispatch and surface composition logic in place.

## Materials

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/renderer_processor.py`
