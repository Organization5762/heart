# Lagom Render Loop Pacer Integration Note

## Problem Statement

The render loop pacing configuration was constructed directly inside
`heart.runtime.game_loop.GameLoop`, which bypassed the runtime container and left pacing
behaviour outside the Lagom wiring path. That made it harder to override pacing defaults
for tests or alternative runtime setups, and it fractured the dependency injection story
for the runtime loop.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/runtime/container.py`,
  `src/heart/runtime/game_loop.py`,
  `src/heart/runtime/render_pacing.py`.

## Notes

The runtime container now registers a singleton provider for
`heart.runtime.render_pacing.RenderLoopPacer` using configuration values from
`heart.utilities.env.Configuration`. `GameLoop` resolves the pacer from the shared
container instead of building it inline, keeping pacing behaviour consistent with the
rest of the runtime dependencies and allowing container overrides to customize the loop
for tests or alternative runtime entry points.
