# Lagom Renderer Resolution Note

## Problem Statement

Renderer configuration modules sometimes attempted to resolve renderers from the `GameLoop`
instance directly, even though the shared Lagom container lives on
`GameLoop.context_container`. This masked where dependency resolution actually happened and
made it easier to bypass the container when new renderers were added.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/navigation/composed_renderer.py`,
  `src/heart/programs/configurations/`.

## Notes

`ComposedRenderer.resolve_renderer` now accepts a resolver protocol that only requires a
`resolve()` method. This keeps the API aligned with Lagom while clarifying that the shared
container is the intended source of renderer instances. Configuration modules now pass
`GameLoop.context_container` directly when resolving renderer classes (for example, in
`src/heart/programs/configurations/halloween_2024.py` and
`src/heart/programs/configurations/life.py`), which avoids accidental container bypasses.

This change keeps renderer wiring consistent with the runtime container built in
`src/heart/runtime/container.py` and helps ensure future renderers resolve through Lagom.
