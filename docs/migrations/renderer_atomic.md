# Atomic renderer migration progress

This note tracks the ongoing migration of `BaseRenderer` subclasses to the
immutable `AtomicBaseRenderer` foundation within `src/heart/renderers/`.
Each entry records the renderer, its consumer expectations, and verification
status so incremental updates stay coordinated.

## Current progress

- Converted renderers:
  - `SpritesheetLoop` (`src/heart/renderers/spritesheet.py`) – reference
    implementation with switch and gamepad consumers.
  - `RenderColor` (`src/heart/renderers/color.py`) – now maintains
    immutable colour state and exposes `set_color` for callers that need to
    refresh the fill value.
  - `TextRendering` (`src/heart/renderers/text.py`) – migrates text
    layout to an immutable state snapshot while preserving switch-driven
    rotation across copy decks.
  - `RenderImage` (`src/heart/renderers/image.py`) – loads assets during
    initialization, caches the scaled surface in renderer state, and remains
    compatible with loops that expect simple blit-only behaviour.
  - `SlideTransitionRenderer` (`src/heart/renderers/slide_transition/renderer.py`) –
    tracks slide offsets atomically while orchestrating transition timing across
    two child renderers via a dedicated provider and state module.
  - `FreeTextRenderer` (`src/heart/renderers/free_text.py`) – stores
    wrapped text layout and font sizing in atomic state while preserving
    phone-text integration.
  - `WaterTitleScreen` (`src/heart/renderers/water_title_screen/renderer.py`) –
    tracks wave animation timing via a provider-driven state stream so consumer
    loops receive consistent offsets across frames.
  - `SpritesheetLoopRandom` (`src/heart/renderers/spritesheet_random.py`)
    – keeps the switch consumer while moving frame counters and screen
    selection into immutable state for per-frame randomisation safety.
  - `Tixyland` (`src/heart/renderers/tixyland/renderer.py`) – carries the
    time-tracking accumulator atomically so shader functions invoked by loops
    receive a deterministic elapsed time value.
  - `Life` (`src/heart/renderers/life.py`) – records the seeded grid
    and latest switch-derived seed in immutable state so cellular automata
    updates remain deterministic across warm-up and loop execution.
  - `SlidingImage` (`src/heart/renderers/sliding_image.py`) – caches
    the scaled surface during initialization and tracks the wrap-around offset
    in atomic state so cube-sized slides remain deterministic for consumers.
    Resetting the renderer now preserves the cached surface so returning to
    scene select screens does not blank the banner animation.
  - `SlidingRenderer` (`src/heart/renderers/sliding_image.py`) – wraps
    a composed renderer while keeping the sliding offset immutable for
    downstream loops that expect predictable frame hand-offs.
  - `Rain` (`src/heart/renderers/pixels.py`) – stores the drop origin
    and vertical sweep position atomically so successive frames don't rely on
    mutable instance attributes between resets.
  - `Slinky` (`src/heart/renderers/pixels.py`) – tracks the falling
    anchor and bounce position in immutable state so loop consumers can safely
    reuse instances without carrying prior frame state.
  - `RandomPixel` (`src/heart/renderers/pixels.py`) – keeps the optional
    override colour in atomic state so brightness adjustments sample a stable
    palette even when instances are re-used.
  - `Border` (`src/heart/renderers/pixels.py`) – stores the configured
    colour atomically so composed scenes can flip border hues without mutating
    shared renderer attributes.
  - `RandomPixel` (`src/heart/renderers/pacman.py`) – aligns the arcade
    palette sampler with atomic state so switch-driven playlists can swap in a
    fixed colour when required.
  - `Border` (`src/heart/renderers/pacman.py`) – migrates the decorative
    outline to atomic colour state while preserving configurable display modes.
  - `Rain` (`src/heart/renderers/pacman.py`) – mirrors the drop state
    tracking used elsewhere so the pacman playlist receives deterministic spawn
    points across loop resets.
  - `Slinky` (`src/heart/renderers/pacman.py`) – keeps the falling
    anchor in atomic state so the animation restarts cleanly when composed in
    arcade sequences.
  - `CombinedBpmScreen` (`src/heart/renderers/combined_bpm_screen/renderer.py`)
    – maintains the swap timer atomically while delegating to metadata and max
    BPM sub-renderers so playlists see deterministic rotation cadence.
  - `MarioRenderer` (`src/heart/renderers/mario.py`) – stores the frame
    counter and shake-triggered loop flag in immutable state, keeping
    accelerometer-driven transitions predictable across resets.
  - `PortholeWindowRenderer` (`src/heart/renderers/porthole_window/renderer.py`)
    – tracks elapsed time in immutable state so cloud drift remains stable when
    the renderer is reset or reused.
  - `HeartTitleScreen` (`src/heart/renderers/heart_title_screen/renderer.py`) –
    keeps the heartbeat toggle and elapsed timing in atomic state so mirrored
    title loops resume a consistent animation cadence after resets.
  - `AvatarBpmRenderer` (`src/heart/renderers/max_bpm_screen/renderer.py`) –
    snapshots the currently leading sensor ID, BPM, and avatar name to guarantee
    composed playlists always pull a coherent frame even when the leader
    changes mid-render.
  - `YoListenRenderer` (`src/heart/renderers/yolisten.py`) – keeps the
    flicker colour, calibration offset, and scroll position in atomic state so
    switch-controlled speed adjustments stay deterministic between resets.
  - `MultiScene` (`src/heart/renderers/multi_scene.py`) – tracks the
    active child index and keyboard edge detection atomically so scene cycling
    via switches and keys remains deterministic for composed playlists.
  - `MetadataScreen` (`src/heart/renderers/metadata_screen/renderer.py`) –
    snapshots per-monitor animation state and battery indicators to deliver
    consistent beat visualisations even as heart rate sensors join or leave.
  - `WaterCube` (`src/heart/renderers/water_cube.py`) – records the
    simulated height field and velocity grid atomically so physics steps produce
    deterministic ripples regardless of renderer reuse.
  - `PixelSunriseRenderer` (`src/heart/renderers/pixel_sunrise.py`) –
    stores the animation epoch atomically while keeping GPU resources cached for
    repeatable shader timing across resets.
  - `PixelModelRenderer` (`src/heart/renderers/pixel_model.py`) – keeps
    the render start time immutable so orbiting camera animation progresses
    predictably while leaving OpenGL assets cached on the renderer instance.
  - `LSystem` (`src/heart/renderers/l_system.py`) – manages grammar
    expansion timing atomically so recursive tree generation advances in
    lockstep with the scheduler.
  - `ThreeDGlassesRenderer` (`src/heart/renderers/three_d_glasses.py`)
    – records the frame timer and index atomically so anaglyph slideshows stay
    in sync after resets.
  - `RendererEventPublisher` and `RendererEventSubscriber`
    (`src/heart/renderers/internal/event_stream.py`) – promote sequence
    counters and latest frames into atomic state so event bus producers and
    consumers resume cleanly across scene transitions.
  - `HilbertScene` (`src/heart/renderers/hilbert_curve/renderer.py`) –
    keeps curve interpolation progress and zoom state in immutable snapshots
    driven by a dedicated provider so morph/zoom cycles stay deterministic.
  - `PacmanGhostRenderer` (`src/heart/renderers/pacman.py`) – keeps the
    chase direction, animation toggle, and sprite position immutable so the
    Pac-Man vignette restarts consistently between playlist entries.
  - `SpritesheetLoop` (`src/heart/renderers/spritesheet/renderer.py`) –
    splits frame sequencing into a provider-managed state stream so input-driven
    pacing and loop progression are stored atomically before rendering.
- Remaining renderers will be migrated iteratively. Track additional updates by
  appending to this list with accompanying test references.

Progress indicator: `[#########################>-]`

## Validation

- `make test`
