# Rendering Output Performance Notes

## Problem

`GameLoop._one_loop` in `src/heart/environment.py` converted the display surface into
NumPy arrays (`pygame.surfarray.array3d` plus a transpose) every frame before sending
images to the device. That conversion allocated large arrays on every loop even when
we already had a PIL image from the render pipeline.

## Adjustment

Reuse the `Image` returned by `__finalize_rendering` for device output, converting it
to RGB only when needed. The legacy NumPy conversion remains as a fallback for cases
where a render surface was not produced.

## Materials

- `src/heart/environment.py` (`GameLoop._one_loop`)
