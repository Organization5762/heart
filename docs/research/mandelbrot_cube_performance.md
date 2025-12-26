# Mandelbrot cube performance notes

## Problem

The mandelbrot cube renderer was allocating a fresh iteration buffer every frame when
calling the converge-time routine. The extra allocation and per-frame memory traffic
showed up as avoidable overhead during rendering, especially on constrained devices.

## Change summary

- Added a Numba helper that writes converge-time results into a caller-provided buffer.
- The cube renderer now stores a reusable iteration buffer in state and reuses it
  each frame before palette lookup.

## Materials

- `src/heart/renderers/mandelbrot/cube_renderer.py`
- `src/heart/renderers/mandelbrot/scene.py`
