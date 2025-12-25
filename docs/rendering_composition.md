# Rendering composition strategies

## Problem Statement

Document how the runtime composes multiple renderer surfaces so maintainers can
compare merge strategies and their trade-offs without digging into the render
loop implementation.

## Materials

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/composition.py`
- `src/heart/runtime/rendering/surface_merge.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/rendering.py`

## Composition flow

The render loop gathers one surface per renderer and then combines those
surfaces into a single composite frame before presenting it. The merge step is
configurable so the runtime can trade parallel merge work against a single
batched blit.

## Merge strategies

### Batched (default)

- Collect all renderer surfaces and queue them into a shared composite surface.
- Use a single batched blit to apply all renderer outputs in order.
- Reuse a cached composite surface to avoid per-frame surface allocation.

**Trade-offs**

- Lower Python call overhead from one batched blit.
- Requires holding renderer surfaces until the composite step completes.
- Avoids mutating any renderer's cached surface.

### In-place

- Use the first renderer surface as the base and blit each additional surface
  into it as they are rendered.

**Trade-offs**

- Avoids an extra composite surface when only a few renderers run together.
- Mutates the first renderer surface, which can complicate surface reuse if
  renderers expect their cached surface to remain unmodified after the frame.
- Still performs repeated blits, so overhead grows with renderer count.

### Adaptive

- Choose `batched` or `in_place` based on recent renderer timing history.
- Favors `in_place` when renderer costs are low to minimize merge overhead.
- Switches to `batched` once renderer costs exceed a configurable threshold.

**Trade-offs**

- Requires recent timing samples to make a decision.
- Produces per-frame decisions that are sensitive to the configured thresholds.

## Runtime configuration

Set `HEART_RENDER_MERGE_STRATEGY` to switch strategies at runtime:

- `batched` (default)
- `in_place`
- `adaptive`

Changing the configuration does not require modifications to renderer
implementations.

When `adaptive` is enabled, tune decisions with:

- `HEART_RENDER_MERGE_COST_THRESHOLD_MS` (total renderer cost threshold)
- `HEART_RENDER_MERGE_SURFACE_THRESHOLD` (minimum renderer count before batching)
