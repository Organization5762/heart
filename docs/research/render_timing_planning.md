# Render timing smoothing and plan refresh

## Problem statement

The render planner computes a full timing snapshot and variant decision every
frame, which adds overhead in the main loop. The timing model is also a
cumulative average, so it adapts slowly to changes in renderer workload. We
want plan decisions to respond to recent timings while reducing per-frame
planning overhead.

## Sources

- "Use the tuning knobs below to reduce socket traffic or control acknowledgement waits when routing frames through the isolated renderer." (`docs/getting_started.md`)
- "Maintain an internal status cache to avoid publishing unchanged lifecycle events." (`docs/api/input_bus.md`)

## Proposed changes

1. Switch renderer timing aggregation to an exponential moving average (EMA)
   option so recent frame timings influence the plan faster.
1. Cache render plans for a short, configurable interval to avoid recomputing
   snapshots every frame when the renderer set is stable.

These changes follow the repository guidance that tunable knobs can reduce
runtime overhead, and that caching avoids redundant work when state does not
change.

## Configuration

- `HEART_RENDER_TIMING_STRATEGY`: `ema` (default) or `cumulative` to control
  timing aggregation.
- `HEART_RENDER_TIMING_EMA_ALPHA`: smoothing factor in `(0, 1]` for EMA.
- `HEART_RENDER_PLAN_REFRESH_MS`: plan refresh cadence in milliseconds.

## Materials list

- `docs/getting_started.md` (Isolated Renderer I/O Tuning section)
- `docs/api/input_bus.md` (Lifecycle signalling section)
- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/utilities/env/rendering.py`
