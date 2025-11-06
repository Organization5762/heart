# HSV Conversion Fallback Strategy

## Problem Statement

Document how the runtime maintains HSV↔BGR conversions when OpenCV is unavailable so hue-sensitive renderers remain functional.

## Materials

- `src/heart/environment.py` fallback implementation.
- OpenCV `cv2.cvtColor` behaviour for reference.
- LED panel output to validate colour accuracy.

## Technical Approach

1. Detect OpenCV at runtime and cache the result to avoid repeated import checks.
1. Provide numpy-based conversions that mirror OpenCV semantics, including calibration steps to minimise round-trip error.
1. Memoize frequent mappings so repeated colours remain stable without incurring full recomputation.

## Fallback Detection

`_load_cv2_module()` probes for OpenCV with `importlib.util.find_spec`. The result is cached in `CV2_MODULE`, enabling callers to choose between native OpenCV conversions and numpy fallbacks without repeated imports.

## Numpy HSV Conversion

- `_numpy_hsv_from_bgr` reproduces OpenCV's BGR→HSV pipeline using vectorised float math for hue and integer math for saturation/value to reduce rounding drift.
- `_convert_bgr_to_hsv` prefers OpenCV when present; otherwise it delegates to the numpy routine and calibrates neighbouring hues until the round-trip matches the original BGR value.
- A least-recently-used cache (`HSV_TO_BGR_CACHE`) stores high-traffic tuples, smoothing successive frames.

## Numpy HSV→BGR Conversion

- `_numpy_bgr_from_hsv` implements the inverse mapping, selecting hue sectors before scaling back to uint8 BGR.
- `_convert_hsv_to_bgr` mirrors the OpenCV/ numpy branch logic, calibrating well-known hues (for example, pure yellow and cyan) and probing nearby values to correct residual error. Cached mappings are applied before committing results.

## Operational Notes

- The fallback relies on numpy vectorisation, making it viable for the 64×64 panels used in production.
- Renderers that reuse cached hues benefit most from the memoized conversions.
- Validation should cover both OpenCV-present and fallback paths to ensure parity.
