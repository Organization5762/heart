# Lagom runtime container bootstrap note

## Problem Statement

Custom Lagom containers passed into `GameLoop` needed ad-hoc wiring to register
core runtime dependencies and provider registrations. That left container
configuration logic split between `GameLoop` and `build_runtime_container`,
which made it easy for callers to miss bindings when they supplied their own
container instance.

## Materials

- Python 3.11 environment with `uv` for dependency management.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/runtime/container.py`,
  `src/heart/runtime/game_loop/core.py`,
  `src/heart/peripheral/core/providers/registry.py`.

## Notes

`configure_runtime_container` now centralizes runtime bindings and provider
registrations for any Lagom container. `build_runtime_container` uses this helper
when it creates a new container, and `GameLoop` calls the same helper when a
custom container is supplied. The shared configuration flow keeps dependency
wiring consistent across default and custom containers while preserving existing
bindings for overrides.
