# Render loop parallelism tuning research note

## Context

The render loop supports multiple compositing algorithms. We added configuration
options so operators can choose the right blend of parallelism and overhead for
their device and workload without editing code.

## Materials

- Runtime configuration via environment variables.
- Source references listed below.

## Findings

- The renderer variant can now be set to `iterative`, `binary`, or `auto`.
  `auto` selects a binary merge only when the renderer count meets a threshold
  and recent renderer timing totals meet the configured cost threshold.
- The binary merge path can cap its thread pool size, reducing scheduling
  overhead on smaller devices.

## Operational guidance

- Use `HEART_RENDER_VARIANT=auto` to default to iterative compositing while
  enabling binary merges for larger renderer stacks.
- Increase `HEART_RENDER_PARALLEL_THRESHOLD` if thread contention is visible
  with only a few renderers.
- Increase `HEART_RENDER_PARALLEL_COST_THRESHOLD_MS` to keep parallelism off
  until renderers are measurably expensive.
- Set `HEART_RENDER_MAX_WORKERS` to cap render merge concurrency on CPUs that
  struggle with large thread pools.

## References

- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/rendering/timing.py`
- `src/heart/utilities/env/rendering.py`
