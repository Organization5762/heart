# Navigation renderer resolution

## Overview

Renderer composition in the navigation layer accepts either renderer instances or
renderer classes. The class forms require a container-backed resolver so that
construction stays centralized. The logic for validating and resolving those
renderer specifications now lives in `src/heart/navigation/renderer_resolution.py`
so that `ComposedRenderer`, `MultiScene`, and `AppController` share consistent
validation and error handling.

## Module responsibilities

- `src/heart/navigation/renderer_resolution.py` defines the `RendererSpec` type,
  the `RendererResolver` protocol, and helper functions for resolving renderer
  specifications with clear context messages.
- `src/heart/navigation/composed_renderer.py` uses the shared helpers to resolve
  its renderer list and to add additional renderers after initialization.
- `src/heart/navigation/multi_scene.py` uses the shared helpers to resolve its
  scene list consistently.
- `src/heart/navigation/app_controller.py` uses the shared helpers when a title
  renderer is provided as a class type.
