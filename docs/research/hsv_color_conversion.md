# HSV Conversion Fallback Strategy

This note documents the HSV/BGR conversion strategy that keeps the renderer functional even when OpenCV is unavailable. The fallback lives in `src/heart/environment.py` alongside the `GameLoop` orchestration code and supports colour-sensitive renderers by mirroring OpenCV's behaviour as closely as possible.【F:src/heart/environment.py†L1-L138】【F:src/heart/environment.py†L138-L207】

## Fallback detection and module loading

- `_load_cv2_module()` uses `importlib.util.find_spec` to probe for OpenCV at runtime, returning `None` if the dependency or its loader is missing.【F:src/heart/environment.py†L1-L33】
- `CV2_MODULE` caches the import result so detection happens once per process. Callers branch on this sentinel to choose between the native OpenCV implementation and the numpy fallback.【F:src/heart/environment.py†L33-L42】

## Pure numpy HSV conversion

- `_numpy_hsv_from_bgr` reproduces OpenCV's BGR→HSV pipeline using float math for hue and integer math for saturation/value, which reduces rounding drift relative to naive conversions.【F:src/heart/environment.py†L42-L93】
- `_convert_bgr_to_hsv` first defers to OpenCV when available. Otherwise, it calls the numpy routine, then calibrates hue by testing neighbouring offsets until the forward/backward round-trip exactly matches the original BGR triple.【F:src/heart/environment.py†L93-L140】
- The function also memoizes high-usage HSV tuples in `HSV_TO_BGR_CACHE`, evicting with an `OrderedDict` LRU policy once more than 4096 entries accumulate. This cache smooths repeated lookups for identical colours in successive frames.【F:src/heart/environment.py†L29-L41】【F:src/heart/environment.py†L118-L138】

## Pure numpy HSV→BGR conversion

- `_numpy_bgr_from_hsv` implements the inverse conversion, translating hue sectors into piecewise RGB formulas before scaling back to uint8 BGR.【F:src/heart/environment.py†L95-L128】
- `_convert_hsv_to_bgr` mirrors the OpenCV branch/fallback split. The numpy path calibrates well-known hues (pure yellow and cyan) to match hardware expectations and then probes a 3×3×3 neighbourhood to correct any remaining round-trip mismatches.【F:src/heart/environment.py†L140-L199】
- After calibration, cached mappings from `HSV_TO_BGR_CACHE` are applied to keep the fallback consistent with previous frames and to reuse hand-tuned corrections discovered earlier in the run.【F:src/heart/environment.py†L29-L41】【F:src/heart/environment.py†L199-L207】

## Operational considerations

- Because the fallback executes per pixel, it benefits from keeping images small (e.g., 64×64 LED panels) and leverages numpy's vectorisation to stay performant without GPU support.【F:src/heart/environment.py†L42-L140】
- When integrating new renderers, prefer HSV manipulations that reuse cached hues to take advantage of the memoized conversions. Testing with and without OpenCV installed helps ensure both code paths stay healthy.【F:src/heart/environment.py†L93-L207】
