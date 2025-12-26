# Lagom Multi-Scene Resolution Note

## Problem Statement

Multi-scene navigation accepted only pre-built renderer instances, which meant container-managed
renderers could not be resolved when composing scenes dynamically. This kept Lagom usage isolated
from the multi-scene workflow and pushed dependency wiring into configuration modules.

## Materials

- Python 3.11 runtime with `uv` for dependency management.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source files: `src/heart/navigation/multi_scene.py`,
  `src/heart/navigation/app_controller.py`,
  `tests/navigation/test_multi_scene_resolution.py`.

## Notes

`MultiScene` now accepts renderer classes in addition to instances and resolves them through the
shared Lagom container when a `renderer_resolver` is provided. `AppController.add_scene` passes its
resolver into new `MultiScene` instances so scenes created through the game loop can opt into
container-backed dependency wiring. The navigation tests verify that class-based scenes resolve
through Lagom and that missing resolvers raise a clear error.
