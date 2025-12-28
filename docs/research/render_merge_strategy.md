# Renderer merge strategy selection

## Summary

The render loop supports a configurable merge strategy that can batch renderer
surfaces into a shared composite surface, merge surfaces in place, or adapt
between the two based on recent renderer timings. The batched path uses a
reusable composite surface and a frame accumulator to reduce per-frame
allocations and Python-level blit calls.

## Observations

- Batched composition keeps renderer-owned surfaces immutable and shifts merging
  into a single surface reuse point.
- In-place merging minimizes extra surfaces but still incurs one blit per
  renderer after the first.
- Adaptive merging picks between batched and in-place strategies based on
  estimated renderer costs and configured thresholds.
- Runtime configuration makes it easier to tune performance without changing
  renderer implementations.

## Implementation notes

- `Configuration.render_merge_strategy` exposes `HEART_RENDER_MERGE_STRATEGY`.
- `RenderPipeline` resolves adaptive strategy decisions using per-renderer
  timing snapshots.
- `SurfaceComposer` reuses a composite surface cache and a `FrameAccumulator` to
  batch blits when the batched strategy is selected.
- The binary render path still parallelizes renderer execution while composing
  surfaces in a single pass for the batched strategy.

## Materials

- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/rendering/composition.py`
- `src/heart/runtime/rendering/surface_merge.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/rendering.py`
