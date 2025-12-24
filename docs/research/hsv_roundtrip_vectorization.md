# HSV round-trip calibration vectorization

## Problem

The numpy fallback for HSV conversion in `heart.environment` corrects hue values by
checking nearby hues until the converted BGR values match the original image. The
previous implementation processed each mismatched pixel in a nested Python loop,
which scaled poorly when many pixels required adjustment.

## Approach

Vectorize the hue search by batching the candidate hue checks across all mismatched
pixels for each offset. The updated loop keeps the same offsets and matching logic
but uses array operations to compare candidate BGR values in bulk, reducing Python
iteration overhead while preserving the calibrated round-trip behaviour. The same
approach is applied to HSV→BGR correction so mismatched pixels are handled in
groups rather than one-at-a-time.

Add a configuration switch to opt into a lighter-weight calibration mode (`fast`)
that skips the neighbourhood search while still applying targeted pure-colour
adjustments. This allows deployments to pick the precision/performance trade-off
without patching the conversion helper.

## Impact

The per-frame fallback conversion now spends less time in Python when the hue
calibration branch is exercised, improving throughput for renderer pipelines that
rely on the numpy conversion path.

## Materials

- `src/heart/environment.py` (HSV calibration loops, mode selection)
- `src/heart/utilities/env.py` (calibration mode configuration)
- `tests/test_environment_core_logic.py` (HSV conversion round-trip coverage)
