# Runtime Navigation Cleanup

## Problem

The runtime still carried several naming and helper layers that no longer matched the
actual frame path after composition moved into `ComposedRenderer`. The main issues were:

- `GameModes` stored title renderers and mode renderers in parallel lists, which made
  navigation depend on index alignment instead of an explicit mode object.
- Scratch rendering still flowed through helper names like `get_scratch_screen` and a
  separate surface provider, even though `ComposedRenderer` now owns composition.
- `RendererVariant` and `RenderLoopPacer` remained in the container and CLI even though
  `GameLoop` no longer used alternate runtime execution paths.

## Outcome

- `GameModes` now stores `ModeEntry(title_renderer, renderer)` values, so selection,
  initialization, and reset paths all operate on one explicit mode record.
- `DisplayContext.create_scratch_context()` now makes the scratch-context contract clear,
  and `ComposedRenderer` performs mirrored tiling directly.
- Runtime container and CLI construction now take only the dependencies the current loop
  actually uses.

## Source Files

- `src/heart/navigation/game_modes.py`
- `src/heart/navigation/composed_renderer.py`
- `src/heart/runtime/display_context.py`
- `src/heart/runtime/container/initialize.py`
- `src/heart/runtime/game_loop/__init__.py`
