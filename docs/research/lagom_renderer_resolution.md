# Lagom Renderer Resolution Note

## Problem Statement

Renderer configuration modules relied on passing `GameLoop.context_container` around when
resolving renderers, which duplicated container plumbing and made it easier to sidestep the
resolver baked into `ComposedRenderer`.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/navigation/composed_renderer.py`,
  `src/heart/programs/configurations/`.

## Notes

`ComposedRenderer.resolve_renderer` accepts a resolver protocol that only requires a
`resolve()` method, and `ComposedRenderer.resolve_renderer_from_container` uses the resolver
provided by `AppController`. Configuration modules now call
`resolve_renderer_from_container()` on the modes returned by `GameLoop.add_mode`, so the
container linkage stays inside the navigation layer instead of being threaded through every
configuration.

This change keeps renderer wiring consistent with the runtime container built in
`src/heart/runtime/container.py` and helps ensure future renderers resolve through Lagom.
