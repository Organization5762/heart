# Mandelbrot cube renderer

## Summary

The Mandelbrot cube renderer maps each cube face to a rotated section of a
virtual sphere and then projects those angles into the Mandelbrot plane. This
allows the four faces in `Cube.sides()` layouts to share a continuous fractal
field that wraps around the device while slowly rotating in time.

## Implementation notes

- The renderer is implemented in
  `src/heart/renderers/mandelbrot/cube_renderer.py` as
  `CubeMandelbrotRenderer`.
- `_build_cube_angles` precomputes azimuth and elevation grids for each face so
  runtime frames only apply a rotation offset.
- `get_mandelbrot_converge_time` from
  `src/heart/renderers/mandelbrot/scene.py` is reused to stay consistent with
  the existing Mandelbrot palette and interior checks.

## Materials

- `src/heart/renderers/mandelbrot/cube_renderer.py`
- `src/heart/renderers/mandelbrot/scene.py`
- `src/heart/device/__init__.py`
