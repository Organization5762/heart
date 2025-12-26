# Render plan refresh strategy toggle

## Problem statement

Render planning currently refreshes on a fixed interval, which means stable
renderer sets still re-enter the planning pipeline even when no input changes
occur. The main loop runs frequently, so those refreshes add overhead that can
be avoided when renderers are static. We want a configurable path that keeps
the current time-based refresh, while allowing an on-change strategy for
deployments that value lower planning overhead.

## Sources

- "Cache render plans for a short, configurable interval to avoid recomputing
  snapshots every frame when the renderer set is stable." (`docs/research/render_timing_planning.md`)
- "Use the tuning knobs below to reduce socket traffic or control
  acknowledgement waits when routing frames through the isolated renderer."
  (`docs/getting_started.md`)

The existing guidance emphasizes configurable tuning knobs to reduce runtime
overhead, which aligns with adding a render plan refresh strategy toggle.

## Proposal

1. Add a refresh strategy enum that supports:
   - `time`: refresh based on the existing time window.
   - `on_change`: refresh only when the renderer signature changes.
1. Wire the strategy into `RenderPlanCache` so the planner can short-circuit
   stable frames without re-planning.
1. Expose the strategy through configuration so deployments can opt into the
   lighter-weight algorithm without changing code.

## Configuration

- `HEART_RENDER_PLAN_REFRESH_STRATEGY`: `time` (default) or `on_change`.
- `HEART_RENDER_PLAN_REFRESH_MS`: refresh cadence for `time`.

## Materials list

- `src/heart/runtime/render_plan_cache.py`
- `src/heart/runtime/render_pipeline.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/rendering.py`
- `docs/research/render_timing_planning.md`
- `docs/getting_started.md`
