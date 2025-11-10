# Atomic renderer migration progress

This note tracks the ongoing migration of `BaseRenderer` subclasses to the
immutable `AtomicBaseRenderer` foundation within `src/heart/display/renderers/`.
Each entry records the renderer, its consumer expectations, and verification
status so incremental updates stay coordinated.

## Current progress

- Converted renderers:
  - `SpritesheetLoop` (`src/heart/display/renderers/spritesheet.py`) – reference
    implementation with switch and gamepad consumers.
  - `RenderColor` (`src/heart/display/renderers/color.py`) – now maintains
    immutable colour state and exposes `set_color` for callers that need to
    refresh the fill value.
  - `TextRendering` (`src/heart/display/renderers/text.py`) – migrates text
    layout to an immutable state snapshot while preserving switch-driven
    rotation across copy decks.
  - `RenderImage` (`src/heart/display/renderers/image.py`) – loads assets during
    initialization, caches the scaled surface in renderer state, and remains
    compatible with loops that expect simple blit-only behaviour.
  - `SlideTransitionRenderer` (`src/heart/display/renderers/slide.py`) – tracks
    slide offsets atomically while orchestrating transition timing across two
    child renderers.
  - `FreeTextRenderer` (`src/heart/display/renderers/free_text.py`) – stores
    wrapped text layout and font sizing in atomic state while preserving
    phone-text integration.
  - `WaterTitleScreen` (`src/heart/display/renderers/water_title_screen.py`) –
    tracks wave animation timing atomically so consumer loops receive
    consistent offsets across frames.
  - `SpritesheetLoopRandom` (`src/heart/display/renderers/spritesheet_random.py`)
    – keeps the switch consumer while moving frame counters and screen
    selection into immutable state for per-frame randomisation safety.
  - `Tixyland` (`src/heart/display/renderers/tixyland.py`) – carries the
    time-tracking accumulator atomically so shader functions invoked by loops
    receive a deterministic elapsed time value.
- Remaining renderers will be migrated iteratively. Track additional updates by
  appending to this list with accompanying test references.

Progress indicator: `[#########>------------]`

## Validation

- `make test`
