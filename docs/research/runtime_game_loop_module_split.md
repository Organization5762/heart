# Runtime GameLoop Module Split

## Problem Statement

The runtime loop, color conversion helpers, and compatibility exports lived in `src/heart/environment.py`, making it harder to reason about runtime orchestration boundaries and color pipeline utilities. We need to separate the runtime loop from renderer color conversion utilities while preserving compatibility imports for existing callers.

## Materials

- Local checkout of this repository.
- Source files:
  - `src/heart/runtime/game_loop.py`
  - `src/heart/renderers/color_conversion.py`
  - `src/heart/environment.py`
  - `src/heart/display/recorder.py`
  - `tests/test_environment_core_logic.py`

## Findings

- `src/heart/runtime/game_loop.py` now holds the `GameLoop` orchestration and `RendererVariant` enum, keeping runtime loop responsibilities in a focused module.
- `src/heart/renderers/color_conversion.py` contains the HSV/BGR conversion cache and numpy-based fallback utilities, keeping rendering-specific utilities with other renderers.
- `src/heart/environment.py` is now a compatibility shim that re-exports `DeviceDisplayMode`, `GameLoop`, and `RendererVariant` from `heart.runtime.game_loop` so legacy imports keep working.
- The tests covering HSV/BGR conversion and render loop selection were updated to import from the new runtime and renderer modules, keeping coverage aligned with the new module layout.
