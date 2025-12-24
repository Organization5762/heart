# Renderer merge strategy selection

## Summary

The render loop now supports a configurable merge strategy that either batches
renderer surfaces into a shared composite surface or merges surfaces in place.
The batched path uses a reusable composite surface and a frame accumulator to
reduce per-frame allocations and Python-level blit calls.

## Observations

- Batched composition keeps renderer-owned surfaces immutable and shifts merging
  into a single surface reuse point.
- In-place merging minimizes extra surfaces but still incurs one blit per
  renderer after the first.
- Runtime configuration makes it easier to tune performance without changing
  renderer implementations.

## Implementation notes

- `Configuration.render_merge_strategy` exposes `HEART_RENDER_MERGE_STRATEGY`.
- `GameLoop` reuses a composite surface cache and a `FrameAccumulator` to batch
  blits when the batched strategy is selected.
- The binary render path still parallelizes renderer execution while composing
  surfaces in a single pass for the batched strategy.

## Materials

- `src/heart/environment.py`
- `src/heart/utilities/env.py`
- `src/heart/renderers/internal/frame_accumulator.py`
