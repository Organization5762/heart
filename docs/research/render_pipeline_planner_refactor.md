# Render pipeline planning helper extraction

## Summary

Move render-variant selection, merge-strategy selection, and planning logs into a
`RenderPlanner` helper so `RenderPipeline` stays focused on dispatch and surface
composition.

## Motivation

`RenderPipeline` was handling variant selection, merge-strategy resolution, and
planning logs alongside executor management and surface composition. Consolidating
these decisions into a planner keeps render dispatch easier to follow while
preserving the same timing-based decisions and structured logs.

## Implementation notes

- Added `RenderPlanner` to resolve render variants and merge strategies using
  timing snapshots and configuration thresholds.
- Centralized render-plan logging in the planner so the same log payload is
  emitted after a plan is selected.
- Updated `RenderPipeline` to delegate merge-strategy selection to the planner
  while continuing to apply the chosen strategy via the composition manager.

## Materials

- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/render/planner.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/runtime/rendering/variants.py`
