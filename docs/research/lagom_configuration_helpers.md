# Lagom configuration helper integration

## Problem Statement

Configuration modules still reached into `GameLoop.context_container` directly and
manually constructed `ComposedRenderer` groups without the shared resolver.
That left some renderer bundles outside the Lagom resolution path and duplicated
container access in multiple configuration files.

## Materials

- Python 3.11 with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/runtime/game_loop/core.py`,
  `src/heart/programs/configurations/lib_2024.py`,
  `src/heart/programs/configurations/lib_2025.py`,
  `src/heart/programs/configurations/tixyland.py`.

## Notes

`GameLoop` now exposes `resolve` and `compose` helpers so configuration modules
can resolve Lagom-managed dependencies and build `ComposedRenderer` groups with a
shared resolver. The loop also applies peripheral provider registrations when a
custom container is supplied, keeping renderer provider bindings consistent even
outside the default builder. Configuration modules now call these helpers
instead of reaching into the container directly, keeping Lagom usage centralized
in the runtime layer.

`ComposedRenderer` now resolves renderer classes passed at construction or via
`add_renderer` when a resolver is available. `AppController` accepts renderer
classes or lists of renderer classes for titles, allowing configuration code to
lean on Lagom for renderer instantiation without reaching into container
internals.
