# Render plan reuse and signature strategy

## Technical problem

The main loop already builds a render plan to pick the render variant, estimate
cost, and capture timing snapshots, but it previously asked the timing tracker
for another estimate after rendering. This repeated estimation work in a hot path.
Additionally, the render-plan cache used instance identifiers for its signature
so it would miss cache hits if renderers were recreated without changing type.

## Approach

- Reuse the render plan produced by the render pipeline for pacing decisions so
  the timing estimate is computed once per frame.
- Make the render plan cache signature strategy configurable so operators can
  trade stricter identity tracking (`instance`) for broader reuse (`type`).

## Configuration

Set `HEART_RENDER_PLAN_SIGNATURE_STRATEGY` to either:

- `instance` (default): signatures track renderer instances.
- `type`: signatures track renderer classes, improving cache reuse when
  renderer instances are replaced but types remain stable.

## Materials

- `src/heart/runtime/game_loop/core.py`
- `src/heart/runtime/render/pipeline.py`
- `src/heart/runtime/render/plan_cache.py`
- `src/heart/utilities/env/rendering.py`
