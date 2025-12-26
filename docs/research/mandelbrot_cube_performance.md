# Mandelbrot Cube Rendering Performance Notes

## Problem statement

The Mandelbrot cube renderer in `src/heart/renderers/mandelbrot/cube_renderer.py` was allocating multiple large arrays every frame (azimuths, real/imag coordinates, palette lookups, and a transposed color buffer). Those allocations added CPU overhead and created extra GC pressure while the scene was animating.

## Approach

- Preallocate per-frame buffers (azimuths, real coordinates, color buffer) inside the renderer state to reuse them across frames.
- Precompute the static imaginary coordinates for the cube faces so they are not recomputed every frame.
- Use NumPy in-place math (`np.add`, `np.multiply`, `np.remainder`, `np.clip`) and `np.take(..., out=...)` to avoid intermediate arrays during rotation, coordinate conversion, and palette lookup.
- Keep a swapped-axis view of the color buffer so `pygame.surfarray.blit_array` can consume it without creating a new transposed array each frame.

## Materials

- `src/heart/renderers/mandelbrot/cube_renderer.py`
- `src/heart/renderers/mandelbrot/scene.py`
