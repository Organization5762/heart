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
  `auto` selects a binary merge only when the renderer count meets a threshold.
- The binary merge path can cap its thread pool size, reducing scheduling
  overhead on smaller devices.

## Operational guidance

- Use `HEART_RENDER_VARIANT=auto` to default to iterative compositing while
  enabling binary merges for larger renderer stacks.
- Increase `HEART_RENDER_PARALLEL_THRESHOLD` if thread contention is visible
  with only a few renderers.
- Set `HEART_RENDER_MAX_WORKERS` to cap render merge concurrency on CPUs that
  struggle with large thread pools.

## References

- `src/heart/environment.py`
- `src/heart/loop.py`
- `src/heart/utilities/env.py`
