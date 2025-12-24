# Navigation module split for clarity

## Summary

The navigation logic previously combined application control, mode switching, composition, and multi-scene state
in a single module. The code is now organized into focused modules under `src/heart/navigation/` so each class
lives with its own state and initialization behavior. This keeps the navigation concerns easier to scan and aligns
with the single-responsibility guidance for core runtime components.

## Notes

- `AppController` and its helpers live in `app_controller.py`.
- Mode state and input handling live in `game_modes.py`.
- Renderer composition lives in `composed_renderer.py`.
- Scene switching logic lives in `multi_scene.py`.
- `src/heart/navigation/__init__.py` preserves the public imports.

## Materials

- `src/heart/navigation/app_controller.py`
- `src/heart/navigation/game_modes.py`
- `src/heart/navigation/composed_renderer.py`
- `src/heart/navigation/multi_scene.py`
- `src/heart/navigation/__init__.py`
