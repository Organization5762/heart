# Spritesheet frame cache research note

## Context

Spritesheet-based renderers were extracting and scaling frames every tick. The
spritesheet loader now provides cached frame extraction and cached scaling to
reduce repeated surface allocation when frame rectangles and target sizes stay
stable.

## Notes

- The loader caches extracted frames by rectangle when the cache strategy is
  `frames` or `scaled`.
- The scaled cache keys on rectangle plus output size when the cache strategy is
  `scaled`.
- Spritesheet renderers request the scaled helper so shared sizes can reuse the
  cached surfaces during rendering.

## Sources

- `src/heart/assets/loader.py`
- `src/heart/utilities/env.py`
- `src/heart/renderers/spritesheet/renderer.py`
- `src/heart/renderers/spritesheet_random/renderer.py`
- `src/heart/renderers/mario/renderer.py`
