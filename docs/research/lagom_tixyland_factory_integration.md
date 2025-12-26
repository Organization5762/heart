# Lagom Tixyland Factory Integration Note

## Problem Statement

Tixyland scenes were created by directly resolving `TixylandStateProvider` in each configuration
module. This repeated container access in multiple places and did not provide a dedicated
factory abstraction for building Tixyland scenes from the runtime container.

## Materials

- Python 3.11 with `uv` for dependency management.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source files: `src/heart/renderers/tixyland/factory.py`,
  `src/heart/renderers/tixyland/__init__.py`,
  `src/heart/programs/configurations/tixyland.py`,
  `src/heart/programs/configurations/lib_2025.py`.

## Notes

`TixylandFactory` is registered with the provider registry so Lagom can resolve a container-backed
factory. Configuration modules now resolve the factory once and reuse it to build Tixyland scenes,
keeping provider wiring inside the container registration and reducing repeated provider
resolution calls in the configurations.
