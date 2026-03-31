# Composed Renderer Runtime Simplification

## Problem Statement

The runtime previously split frame execution across `GameLoop`, `AppController`,
`RenderPipeline`, and `RendererProcessor`. That made the control flow harder to
trace and left composition semantics duplicated in both the navigation and runtime
layers.

## Materials

- `src/heart/runtime/game_loop/__init__.py`
- `src/heart/navigation/game_modes.py`
- `src/heart/navigation/composed_renderer.py`
- `src/heart/runtime/container/initialize.py`

## Notes

The runtime now has one navigation layer and one composition layer.

- `GameModes` owns mode registration, title scenes, low-power mode setup, and
  mode-selection state.
- `ComposedRenderer` owns scratch-surface execution, mirrored tiling, child
  renderer initialization, and child surface merging.
- `GameLoop` owns top-level display-mode selection, post-processing, and final
  presentation.
- The Lagom container still resolves default renderer classes, but the resolver is
  passed explicitly into `ComposedRenderer` and `GameModes` instead of being hidden
  on unrelated helper objects.

This keeps large renderers such as Mandelbrot and the 3D fractal as leaf modules:
they only need to implement renderer lifecycle and declare their display mode,
while the runtime stays focused on orchestration.
