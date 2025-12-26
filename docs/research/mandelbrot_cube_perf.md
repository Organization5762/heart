# Mandelbrot Cube Performance Notes

## Problem

The cube renderer recomputes trigonometric rotations and allocates larger-than-needed buffers each frame. This can add CPU cost and memory bandwidth pressure during rendering.

## Observations

- `CubeMandelbrotRenderer` updates azimuths with a per-frame rotation and feeds the results into a Numba kernel for iteration counts.
- The base cube geometry is static; only rotation changes per frame.
- The iteration buffer does not need 32-bit storage at the current iteration caps.

## Changes

- Reused computed elevation values across cube faces instead of recomputing the arcsin per face.
- Shifted scalar constants to `float32` to keep array math in lower precision.
- Reduced the iteration buffer to `uint16` to lower memory bandwidth during iteration writes.

## Materials

- `src/heart/renderers/mandelbrot/cube_renderer.py`
- `src/heart/renderers/mandelbrot/scene.py`
