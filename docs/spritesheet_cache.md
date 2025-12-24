# Spritesheet frame cache

## Problem

Spritesheet renderers repeatedly extract rectangles and scale them to the same
sizes each frame. That work reallocates surfaces and can be avoided when frame
sizes repeat.

## Behavior

The spritesheet loader can reuse extracted frames and scaled frames based on a
cache strategy. The cache keys on the source rectangle, and the scaled cache adds
in the requested output size. Renderers request the scaled cache helper so shared
frame sizes can reuse the same surface between ticks.

## Configuration

Set `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY` to choose a cache mode:

- `scaled` caches extracted frames and scaled surfaces (default).
- `frames` caches extracted frames only.
- `none` disables spritesheet frame caching.

## Materials

- Environment variable: `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY`.
- Spritesheet assets loaded via `src/heart/assets/loader.py`.
