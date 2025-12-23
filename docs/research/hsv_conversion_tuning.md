# HSV conversion tuning research note

## Context

The HSV/BGR conversion helpers in `src/heart/environment.py` include a
calibration pass that adjusts hue values and a per-pixel neighbourhood search to
match OpenCV conversions when OpenCV is not available. Those calibration passes
are accurate but can add CPU overhead for large frames. The same module also
maintains an HSV-to-BGR LRU cache to speed up repeated colors, which has its own
memory footprint and update cost.

## Decision

Expose configuration for the calibration pass and the cache size so deployments
can trade accuracy for throughput and memory usage.

## Sources

- `src/heart/environment.py` (HSV/BGR conversion, cache maintenance, calibration)
- `src/heart/utilities/env.py` (runtime configuration helpers)
