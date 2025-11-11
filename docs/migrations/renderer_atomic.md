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
  - `Life` (`src/heart/display/renderers/life.py`) – records the seeded grid
    and latest switch-derived seed in immutable state so cellular automata
    updates remain deterministic across warm-up and loop execution.
  - `SlidingImage` (`src/heart/display/renderers/sliding_image.py`) – caches
    the scaled surface during initialization and tracks the wrap-around offset
    in atomic state so cube-sized slides remain deterministic for consumers.
    Resetting the renderer now preserves the cached surface so returning to
    scene select screens does not blank the banner animation.
  - `SlidingRenderer` (`src/heart/display/renderers/sliding_image.py`) – wraps
    a composed renderer while keeping the sliding offset immutable for
    downstream loops that expect predictable frame hand-offs.
  - `Rain` (`src/heart/display/renderers/pixels.py`) – stores the drop origin
    and vertical sweep position atomically so successive frames don't rely on
    mutable instance attributes between resets.
  - `Slinky` (`src/heart/display/renderers/pixels.py`) – tracks the falling
    anchor and bounce position in immutable state so loop consumers can safely
    reuse instances without carrying prior frame state.
  - `RandomPixel` (`src/heart/display/renderers/pixels.py`) – keeps the optional
    override colour in atomic state so brightness adjustments sample a stable
    palette even when instances are re-used.
  - `Border` (`src/heart/display/renderers/pixels.py`) – stores the configured
    colour atomically so composed scenes can flip border hues without mutating
    shared renderer attributes.
  - `RandomPixel` (`src/heart/display/renderers/pacman.py`) – aligns the arcade
    palette sampler with atomic state so switch-driven playlists can swap in a
    fixed colour when required.
  - `Border` (`src/heart/display/renderers/pacman.py`) – migrates the decorative
    outline to atomic colour state while preserving configurable display modes.
  - `Rain` (`src/heart/display/renderers/pacman.py`) – mirrors the drop state
    tracking used elsewhere so the pacman playlist receives deterministic spawn
    points across loop resets.
  - `Slinky` (`src/heart/display/renderers/pacman.py`) – keeps the falling
    anchor in atomic state so the animation restarts cleanly when composed in
    arcade sequences.
  - `CombinedBpmScreen` (`src/heart/display/renderers/combined_bpm_screen.py`)
    – maintains the swap timer atomically while delegating to metadata and max
    BPM sub-renderers so playlists see deterministic rotation cadence.
  - `MarioRenderer` (`src/heart/display/renderers/mario.py`) – stores the frame
    counter and shake-triggered loop flag in immutable state, keeping
    accelerometer-driven transitions predictable across resets.
- Remaining renderers will be migrated iteratively. Track additional updates by
  appending to this list with accompanying test references.

Progress indicator: `[#####################-->-]`

## Validation

- `make test`
