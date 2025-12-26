# Lagom Navigation Renderer Resolution Note

## Problem Statement

Navigation-generated `ComposedRenderer` instances had no default access to the runtime Lagom
container, so renderers could only be resolved when configuration modules passed the container
explicitly. This left navigation-owned renderers outside the shared container context and made it
harder to resolve renderers inside the controller lifecycle.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/navigation/app_controller.py`,
  `src/heart/navigation/composed_renderer.py`,
  `src/heart/runtime/container.py`.

## Notes

`AppController` now accepts a renderer resolver and wires it into newly created
`ComposedRenderer` instances, so navigation-owned renderers can resolve dependencies through the
shared container without additional plumbing. `ComposedRenderer` exposes
`resolve_renderer_from_container` to use its bound resolver when available, while the existing
`resolve_renderer` API remains for explicit resolution in configuration modules.
