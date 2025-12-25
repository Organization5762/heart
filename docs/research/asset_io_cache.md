# Asset IO cache research note

## Problem

Repeated asset decoding and JSON parsing costs add latency when renderers
reinitialize or when multiple providers request the same files. These IO costs
compound during loops that construct renderers repeatedly.

## Observations

- `heart.assets.loader.Loader.load_spirtesheet` creates a `spritesheet` object
  that reads image bytes and decodes the surface (`src/heart/assets/loader.py`).
- `heart.assets.loader.Loader.load` decodes image surfaces for static assets
  (`src/heart/assets/loader.py`).
- JSON metadata for spritesheets is parsed on every `Loader.load_json` call
  (`src/heart/assets/loader.py`, `src/heart/renderers/spritesheet/provider.py`).
- Frame-level caches already exist inside the spritesheet helper, so keeping the
  spritesheet object alive preserves those per-rectangle caches
  (`src/heart/assets/loader.py`).

## Update

Introduce a loader-level asset cache with a bounded LRU policy so spritesheets
and JSON metadata can be reused across renderers. The cache is configurable
through environment variables to allow deployments to trade memory for IO
latency in a controlled way.

## Materials

- `src/heart/assets/cache.py` (LRU container for asset reuse).
- `src/heart/assets/loader.py` (spritesheet and metadata loading).
- `src/heart/utilities/env/assets.py` (configuration parsing).
- `docs/spritesheet_cache.md` (configuration summary for cache strategies).
