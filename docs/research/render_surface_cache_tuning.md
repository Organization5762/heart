# Render surface cache tuning research note

## Context

Renderer frames allocate multiple pygame surfaces per tick. Reusing those buffers
reduces per-frame allocations and lets the render loop focus on drawing rather
than memory churn. The tiling step can also avoid nested Python loops by using
batched blits.

## Materials

- Runtime configuration via environment variables.
- Source references listed below.

## Findings

- Surface reuse is guarded by a new `HEART_RENDER_SURFACE_CACHE` flag so the
  allocation strategy can be toggled per deployment.
- The tiling algorithm now supports a `blits` strategy that batches tile copies
  in pygame, and a `loop` strategy that preserves the prior nested loop.

## Operational guidance

- Keep `HEART_RENDER_SURFACE_CACHE=true` when memory pressure is acceptable and
  the renderer spends time allocating surfaces.
- Switch `HEART_RENDER_TILE_STRATEGY=loop` if the batched blit path causes
  issues on a specific device.

## References

- `src/heart/renderers/__init__.py`
- `src/heart/utilities/env.py`
