# Renderer file structure refactor

The renderer refactor cleaned up remaining monolithic modules so each renderer now follows the provider/state/renderer pattern used by Water and Life.

- `three_fractal` now lives in `src/heart/renderers/three_fractal/` with a provider that creates the OpenGL runtime state and a renderer wrapper that delegates frames to that runtime.
- Legacy single-file modules for `hilbert_curve` and `spritesheet` were removed in favor of their existing package-structured implementations.
