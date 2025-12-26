# Lagom Renderer Provider Integration Note

## Problem Statement

Renderer configurations still constructed some provider-backed renderers manually, which bypassed
Lagom and duplicated wiring for `PeripheralManager` and `Device`. This left provider-based
renderers outside the shared container path and made configuration code responsible for repeating
DI concerns.

## Materials

- Python 3.11 with `uv` for dependency management.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source files: `src/heart/renderers/multicolor/`,
  `src/heart/renderers/cloth_sail/`,
  `src/heart/renderers/three_fractal/`,
  `src/heart/renderers/mario/`,
  `src/heart/programs/configurations/lib_2025.py`,
  `src/heart/programs/configurations/l_system.py`,
  `src/heart/programs/configurations/porthole_window.py`,
  `src/heart/programs/configurations/cloth_sail.py`.

## Notes

`MulticolorStateProvider`, `ClothSailStateProvider`, `FractalSceneProvider`, and
`MarioRendererProvider` are now registered with the shared provider registry so Lagom can resolve
them from the runtime container. The corresponding renderers now require injected providers, and
configuration modules resolve those renderers through `GameLoop.context_container` instead of
manually constructing providers. The Fractal scene provider now takes a `Device` dependency from
the container, which keeps device wiring centralized in `build_runtime_container` and avoids
leaking device plumbing into configuration modules.

`LSystem` and `PortholeWindowRenderer` configurations now rely on
`ComposedRenderer.resolve_renderer_from_container` so Lagom supplies the registered state
providers. This reduces direct provider construction in configuration modules while keeping the
runtime container responsible for provider wiring.
