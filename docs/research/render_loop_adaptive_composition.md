# Render loop adaptive composition research note

## Context

The render loop can now make compositing decisions based on recent renderer
timings, so operators can reduce scheduling overhead on small devices without
removing parallel options for heavy scenes.

## Materials

- Runtime timing snapshots recorded per renderer.
- Environment configuration for render variant and merge strategy thresholds.
- Source references listed below.

## Findings

- The pipeline records a rolling average and last duration for each renderer
  and uses those totals to estimate the next frame cost.
- `RendererVariant.AUTO` now relies on both renderer count and cost estimates to
  decide between iterative and binary composition.
- `RenderMergeStrategy.ADAPTIVE` switches between in-place and batched merges
  using the same timing data.

## Operational guidance

- Use `HEART_RENDER_VARIANT=auto` with `HEART_RENDER_PARALLEL_COST_THRESHOLD_MS`
  tuned to the total render time where parallel work becomes worthwhile.
- Use `HEART_RENDER_MERGE_STRATEGY=adaptive` with
  `HEART_RENDER_MERGE_COST_THRESHOLD_MS` and
  `HEART_RENDER_MERGE_SURFACE_THRESHOLD` to keep small stacks on the in-place
  path.
- Confirm `render.plan` logs include per-renderer timing snapshots when tuning
  thresholds.

## References

- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/runtime/rendering/surface_merge.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/rendering.py`
