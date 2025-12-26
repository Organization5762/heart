# Lagom GameLoop container resolution note

## Problem Statement

Runtime entrypoints still instantiated `GameLoop` directly, which bypassed the Lagom
container even though the container already wired core runtime services. This left the
entrypoint responsible for choosing constructor parameters instead of letting the
container own the wiring, and it made it harder to keep `GameLoop` construction aligned
with container overrides in tests.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/runtime/container.py`,
  `src/heart/runtime/game_loop.py`,
  `src/heart/cli/commands/game_loop.py`,
  `tests/runtime/test_container.py`.

## Notes

`build_runtime_container` now registers `GameLoop` as a singleton resolved through Lagom,
so entrypoints can request `GameLoop` from the container instead of wiring it manually.
The CLI game loop builder uses `resolver.resolve(GameLoop)` to keep runtime creation
aligned with container overrides, and the container tests assert that `GameLoop` is
resolved from the same container instance.
