# HSV conversion tuning

The HSV/BGR conversion helpers in `heart.environment` prioritize accuracy by
calibrating numpy conversions to match OpenCV output and by maintaining a small
LRU cache for recent colors. On constrained devices or when rendering large
frames, that calibration and cache management can become a noticeable portion of
frame time. The settings below let you trade accuracy for throughput when
needed.

## Environment variables

- `HEART_HSV_CALIBRATION` (default: `true`)
  - When set to `false`, disables the hue-roundtrip correction and the per-pixel
    neighbourhood search that aligns numpy conversion output with OpenCV.
  - This reduces per-frame CPU work at the cost of exact round-trip accuracy.
- `HEART_HSV_CACHE_MAX_SIZE` (default: `4096`)
  - Sets the maximum number of HSV-to-BGR entries stored in the in-memory LRU
    cache.
  - Set to `0` to disable cache population and lookup entirely.
- `HEART_HSV_BACKEND` (default: `auto`)
  - Chooses the implementation for HSV/BGR conversions.
  - `auto` uses OpenCV when available and falls back to numpy otherwise.
  - `numpy` forces the numpy implementation even when OpenCV is available.
  - `cv2` requires OpenCV and fails fast if the module is unavailable.

## Materials

- Environment variables: `HEART_HSV_CALIBRATION`, `HEART_HSV_CACHE_MAX_SIZE`,
  `HEART_HSV_BACKEND`.
- Source: `src/heart/environment.py`.
