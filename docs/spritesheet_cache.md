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

Set `HEART_ASSET_CACHE_STRATEGY` to configure loader-level caching:

- `all` caches spritesheets and parsed JSON metadata (default).
- `images` caches loaded image surfaces only.
- `spritesheets` caches spritesheet objects only.
- `metadata` caches parsed JSON metadata only.
- `none` disables loader-level asset caching.

Use `HEART_ASSET_CACHE_MAX_ENTRIES` to cap the number of cached items
per asset type. Set `0` to disable caching without changing the strategy
value.

Set `HEART_ASSET_IO_CACHE_STRATEGY` to cache raw asset bytes and reduce disk IO:

- `all` caches bytes for images, spritesheets, and metadata (default).
- `images` caches image file bytes only.
- `spritesheets` caches spritesheet file bytes only.
- `metadata` caches JSON file bytes only.
- `none` disables the IO byte cache.

Use `HEART_ASSET_IO_CACHE_MAX_ENTRIES` to cap the number of cached byte
entries per asset type. Set `0` to disable byte caching without changing
the strategy value.

## Materials

- Environment variable: `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY`.
- Environment variables: `HEART_ASSET_CACHE_STRATEGY`,
  `HEART_ASSET_CACHE_MAX_ENTRIES`.
- Environment variables: `HEART_ASSET_IO_CACHE_STRATEGY`,
  `HEART_ASSET_IO_CACHE_MAX_ENTRIES`.
- Spritesheet assets loaded via `src/heart/assets/loader.py`.
