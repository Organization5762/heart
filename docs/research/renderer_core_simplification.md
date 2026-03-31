# Renderer Core Simplification

## Problem Statement

Several renderer modules carried leftover forwarding methods and helper wrappers that no longer added behavior. The renderer core also modeled post-processors as reactive stateful renderers even though they only needed direct access to the active `PeripheralManager`. That extra structure made the renderer layer harder to read and easier to drift.

## Materials

- `src/heart/renderers/stateful.py`
- `src/heart/renderers/post_processing.py`
- `src/heart/navigation/game_modes.py`
- `src/heart/renderers/sliding_image/renderer.py`
- `src/heart/renderers/spritesheet/renderer.py`
- `src/heart/renderers/image/renderer.py`
- `src/heart/renderers/text/renderer.py`

## Notes

- Renderers that only forwarded `state_observable()` to `builder.observable(peripheral_manager)` now rely on `StatefulBaseRenderer` directly instead of repeating the same wrapper method.
- `SlidingImage` and `SlidingRenderer` now construct their providers directly instead of routing through single-use `_default_provider()` helpers.
- The dead `create_spritesheet_loop()` factory and its export were removed because it referenced a renderer API that no longer exists.
- Post-processors now keep the active `PeripheralManager` on the renderer instance and manage initialization/reset locally instead of creating unused state dataclasses and faux reactive initialization paths.
- `GameModes` now installs only the real post-processors and no longer carries the unused `handle_state()` navigation path.

## Sources

- `src/heart/renderers/post_processing.py`
- `src/heart/navigation/game_modes.py`
- `src/heart/renderers/sliding_image/renderer.py`
- `src/heart/renderers/spritesheet/renderer.py`
- `src/heart/renderers/image/renderer.py`
- `src/heart/renderers/text/renderer.py`
