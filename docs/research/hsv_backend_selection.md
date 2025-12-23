# HSV backend selection and calibration batching

## Context

HSV/BGR conversion in `heart.environment` is part of the core render loop. The
numpy path includes calibration steps to align with OpenCV outputs, and those
steps can dominate frame time when many pixels need correction. The system also
implicitly picked OpenCV whenever the module was installed, which made it hard
to compare backends or enforce a deterministic path during performance testing.

## Findings

- The per-pixel neighbourhood search used during HSV-to-BGR calibration can be
  batched across all mismatches to reduce Python-level loops.
- Selecting the HSV conversion backend should be configurable so that
  deployments can opt into numpy-only behaviour or require OpenCV explicitly.

## Decision

- Batch the HSV-to-BGR calibration search so mismatches are resolved in a single
  vectorized pass, reducing Python-level looping in the hot path.
- Introduce a `HEART_HSV_BACKEND` environment variable to allow `auto`, `numpy`,
  or `cv2` selection of the conversion backend.

## Follow-up

- Track render-loop timing with and without OpenCV to quantify the benefit of
  each backend on target hardware.

## Materials

- `src/heart/environment.py`
- `src/heart/utilities/env.py`
- `docs/color_conversion_tuning.md`
