# Spritesheet Frame Cache Strategy Research Note

## Context

Spritesheet-based renderers (`heart.renderers.spritesheet`,
`heart.renderers.spritesheet_random`, and `heart.modules.mario`) repeatedly
extract frames from a spritesheet surface and scale them each tick. This work is
repeated even when a frame and target size remain unchanged for multiple ticks.

## Observations

- `heart.assets.loader.spritesheet.image_at` previously created a new surface and
  blitted the sheet every call, which repeated work for identical frame
  rectangles.
- Renderers scaled the same frame to the same target size on every tick, which
  is redundant when the target size is static.

## Proposed approach

Cache raw spritesheet frames by rectangle, and optionally cache scaled versions
keyed by rectangle and target size. Make the strategy selectable so deployments
can trade memory usage for fewer per-frame allocations.

## Source references

- `src/heart/assets/loader.py`
- `src/heart/renderers/spritesheet/renderer.py`
- `src/heart/renderers/spritesheet_random/renderer.py`
- `src/heart/modules/mario/renderer.py`

## Materials

None.
