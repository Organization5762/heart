# Render plan refresh when timing updates

## Technical problem

With render plan caching configured to refresh only on renderer signature
changes, adaptive planning can stall when the renderer set stays constant.
Timing samples update after rendering, but cached plans do not notice the new
timing state, so adaptive merge or variant selection can remain locked to an
initial estimate for an entire session.

## Approach

- Track a monotonic version counter in the timing tracker that increments when
  timing samples are recorded.
- Store the timing version used for a cached plan and invalidate the cache when
  newer timing data exists.

## Materials

- `src/heart/runtime/rendering/timing.py`
- `src/heart/runtime/render/plan_cache.py`
- `src/heart/runtime/render/planner.py`
