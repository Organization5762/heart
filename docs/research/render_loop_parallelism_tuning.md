# Render loop parallelism tuning research note

## Context

The render loop supports multiple compositing algorithms. We added configuration
options so operators can choose the right blend of parallelism and overhead for
their device and workload without editing code.

## Materials

- Runtime configuration via environment variables.
- Source references listed below.

## Findings

- The renderer variant supports `iterative`, `binary`, `auto`, and `adaptive`.
  `auto` selects a binary merge only when the renderer count meets a threshold.
  `adaptive` uses a rolling estimate of per-renderer cost to decide when the
  binary merge path should take over.
- The binary merge path can cap its thread pool size, reducing scheduling
  overhead on smaller devices.

## Operational guidance

- Use `HEART_RENDER_VARIANT=auto` to default to iterative compositing while
  enabling binary merges for larger renderer stacks.
- Use `HEART_RENDER_VARIANT=adaptive` to switch based on estimated render cost
  rather than only renderer count.
- Increase `HEART_RENDER_PARALLEL_THRESHOLD` if thread contention is visible
  with only a few renderers.
- Tune `HEART_RENDER_PARALLEL_COST_THRESHOLD_MS` to change the estimated render
  cost required before binary merges become the default.
- Use `HEART_RENDER_PARALLEL_COST_DEFAULT_MS` to set the estimated cost of new
  renderers before any measurements are available.
- Adjust `HEART_RENDER_PARALLEL_COST_SMOOTHING` when you need render cost
  estimates to react more quickly or more slowly to changes.
- Set `HEART_RENDER_MAX_WORKERS` to cap render merge concurrency on CPUs that
  struggle with large thread pools.

## References

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/variants.py`
- `src/heart/utilities/env/rendering.py`
