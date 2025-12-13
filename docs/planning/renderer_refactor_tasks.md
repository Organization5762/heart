# Renderer refactor rollout

## Problem Statement

The renderer catalogue mixes several structural patterns, leaving many entries as monolithic files that entwine input handling, state mutation, and draw logic. This inconsistency slows maintenance, complicates testing, and makes it difficult to compose renderers safely with shared peripherals. We need every renderer to adopt the provider/state/renderer split already used by the Water and Doppler pipelines so lifecycle hooks, subscriptions, and state ownership stay predictable.

## Materials

- Source renderers in `src/heart/display/renderers/`
- Peripheral observables from `heart.peripheral.core.manager.PeripheralManager`
- Base classes in `heart.display.renderers.__init__` (AtomicBaseRenderer, StatefulBaseRenderer, ComposedRenderer)
- Reactivex operators for streaming state updates
- Asset loader utilities in `heart.assets.loader.Loader`
- Existing refactored examples: `water_title_screen`, `random_pixel`, `led_wave_boat`, `slide_transition`, `text`, `max_bpm_screen`
- CI hooks and formatters invoked via `make format` and `make test`

## Opening abstract

We will iterate through the remaining renderers and restructure each into three files—`provider.py` for observable assembly, `state.py` for immutable dataclasses, and `renderer.py` for draw logic. The refactors will keep existing visuals intact while aligning lifecycle management with `StatefulBaseRenderer` or Atomic equivalents wired to providers. By converging on this pattern, follow-on maintenance, composition with playlists, and subscription cleanup become routine rather than ad hoc. The work proceeds renderer-by-renderer with checkpoints for shared assets and dependency reuse.

## Success criteria table

| Criterion | Validation signal | Owner |
| --- | --- | --- |
| Every unrefactored renderer moved into a three-file package with `__init__.py` exporting the renderer class | File tree shows package directories per renderer with provider/state/renderer modules; imports updated without runtime regressions | Renderer maintainers |
| Providers stream state through observables or deterministic polling without side effects in draw loops | Unit or smoke tests show stable frame rendering with no direct peripheral reads inside `real_process` | Contributors performing refactors |
| Subscriptions and disposables cleaned up on reset to prevent leaks | Profiling or manual inspection confirms subscriptions disposed when renderer reset | Contributors performing refactors |
| Documentation updated for each migration with rationale and touchpoints | `docs/migrations` entries reflect new paths and structures | Documentation owners |

## Task breakdown checklists

### Discovery

- [ ] Confirm current behaviour and dependencies for each renderer before refactoring by reading existing modules and noting asset requirements.
- [ ] Identify shared provider patterns (e.g., switch state, clock tick, BPM feeds) that can be reused across renderers to minimise duplicate logic.

### Implementation

- [ ] `artist.py`: split into package with state capturing palette/position, provider handling input, and renderer drawing art frames.
- [ ] `cloth_sail.py`: extract wind/oscillation parameters into state; provider streams physics deltas; renderer handles mesh drawing.
- [ ] `color.py`: encapsulate colour transitions and timing in state; provider emits colour steps; renderer applies fills.
- [ ] `combined_bpm_screen.py`: move playlist rotation and metadata/max-BPM coordination into provider/state split with a composed renderer wrapper.
- [ ] `flame.py`: isolate flame simulation parameters in state; provider drives frame progression; renderer focuses on blitting frames.
- [ ] `free_text.py`: capture text content, cursor, and colour in state; provider consumes switch/keyboard events; renderer renders glyphs only.
- [ ] `heart_title_screen.py`: separate heartbeat timing and toggles into state; provider handles clock-driven pulses; renderer draws title art.
- [ ] `hilbert_curve.py`: keep iteration depth and traversal index in state; provider advances steps from tick stream; renderer paints curve segments.
- [ ] `image.py`: manage image selection and fade state separately; provider cycles assets; renderer handles surface composition.
- [ ] `kirby.py`: move animation frame index and physics to state; provider ticks movement and sprite selection; renderer blits sprites.
- [ ] `l_system.py`: encapsulate grammar expansion progress in state; provider steps production rules on ticks; renderer plots lines.
- [ ] `metadata_screen.py`: keep per-sensor values and layout toggles in state; provider ingests BPM/metadata streams; renderer draws HUD.
- [ ] `multicolor.py`: track palette rotation and transition timing in state; provider sequences colours; renderer applies fills.
- [ ] `pacman.py`: split ghost/player state into dataclasses; provider advances movement and collisions; renderer draws tiles and sprites.
- [ ] `pixels.py`: capture pixel set and animation offset in state; provider selects pixels based on peripherals; renderer blits points.
- [ ] `porthole_window.py`: move cloud drift timers and offsets into state; provider steps movement with clock ticks; renderer draws viewport.
- [ ] `sliding_image.py`: separate slide position and timing into state; provider handles sequencing; renderer performs transitions.
- [ ] `spritesheet.py`: wrap frame index and looping configuration in state; provider advances frames; renderer composes spritesheet frames.
- [ ] `spritesheet_random.py`: store random sequence seeds and current frame in state; provider produces deterministic frame order; renderer blits frames.
- [ ] `three_d_glasses.py`: keep frame timer and slide index in state; provider controls timing; renderer handles stereo composition.
- [ ] `three_fractal.py`: manage fractal parameters and zoom state; provider updates iterations; renderer draws fractal tiles.
- [ ] `tixyland.py`: store expression selections and phase in state; provider evaluates formulas per tick; renderer paints grid outputs.
- [ ] `yolisten.py`: capture colour/scroll offsets in state; provider responds to audio input or sensor triggers; renderer paints waveform visuals.

### Validation

- [ ] For each renderer, run smoke tests or targeted loops to verify visuals match pre-refactor output.
- [ ] Ensure providers unsubscribe or dispose resources in `reset` to avoid dangling observers.
- [ ] Update `docs/migrations` with new paths and summary notes for each completed refactor.
- [ ] Execute `make format` and `make test` after batches to keep formatting and regression coverage aligned.

## Narrative walkthrough

Refactors start with a quick audit to understand the renderer’s inputs (switches, audio, BPM, file assets) and outputs (sprites, gradients, text). For each module we carve out an immutable `state.py` dataclass that expresses the frame prerequisites such as timers, indices, palette choices, or offsets. A `provider.py` then assembles observables from `PeripheralManager` (clock ticks, switch streams, heart rate feeds) to emit new state snapshots—generally through `scan`, `map`, and `start_with` operators. The `renderer.py` focuses solely on drawing based on the current state, deferring all mutation to provider-driven updates. Where compositional patterns appear (e.g., playlists combining multiple renderers), the composed wrapper should wire each child renderer’s provider so subscriptions start during initialisation and dispose in `reset`.

Each task listed above follows this recipe but adapts to renderer-specific behaviour: physics-based scenes (cloth, pacman, kirby) rely on deterministic `scan` updates, while UI scenes (metadata, heart title, free text) mainly map peripheral input streams to state changes. Using the Water and Max BPM refactors as references, each provider should share observables to avoid duplicate work when multiple subscribers appear. The checklist approach keeps individual refactors independent while moving the entire catalogue toward the same lifecycle model.

## Visual reference

| Renderer | Current location | Target package layout |
| --- | --- | --- |
| artist | `src/heart/display/renderers/artist.py` | `artist/{provider.py,state.py,renderer.py}` |
| cloth_sail | `src/heart/display/renderers/cloth_sail.py` | `cloth_sail/{provider.py,state.py,renderer.py}` |
| color | `src/heart/display/renderers/color.py` | `color/{provider.py,state.py,renderer.py}` |
| combined_bpm_screen | `src/heart/display/renderers/combined_bpm_screen.py` | `combined_bpm_screen/{provider.py,state.py,renderer.py}` |
| flame | `src/heart/display/renderers/flame.py` | `flame/{provider.py,state.py,renderer.py}` |
| free_text | `src/heart/display/renderers/free_text.py` | `free_text/{provider.py,state.py,renderer.py}` |
| heart_title_screen | `src/heart/display/renderers/heart_title_screen.py` | `heart_title_screen/{provider.py,state.py,renderer.py}` |
| hilbert_curve | `src/heart/display/renderers/hilbert_curve.py` | `hilbert_curve/{provider.py,state.py,renderer.py}` |
| image | `src/heart/display/renderers/image.py` | `image/{provider.py,state.py,renderer.py}` |
| kirby | `src/heart/display/renderers/kirby.py` | `kirby/{provider.py,state.py,renderer.py}` |
| l_system | `src/heart/display/renderers/l_system.py` | `l_system/{provider.py,state.py,renderer.py}` |
| metadata_screen | `src/heart/display/renderers/metadata_screen.py` | `metadata_screen/{provider.py,state.py,renderer.py}` |
| multicolor | `src/heart/display/renderers/multicolor.py` | `multicolor/{provider.py,state.py,renderer.py}` |
| pacman | `src/heart/display/renderers/pacman.py` | `pacman/{provider.py,state.py,renderer.py}` |
| pixels | `src/heart/display/renderers/pixels.py` | `pixels/{provider.py,state.py,renderer.py}` |
| porthole_window | `src/heart/display/renderers/porthole_window.py` | `porthole_window/{provider.py,state.py,renderer.py}` |
| sliding_image | `src/heart/display/renderers/sliding_image.py` | `sliding_image/{provider.py,state.py,renderer.py}` |
| spritesheet | `src/heart/display/renderers/spritesheet.py` | `spritesheet/{provider.py,state.py,renderer.py}` |
| spritesheet_random | `src/heart/display/renderers/spritesheet_random.py` | `spritesheet_random/{provider.py,state.py,renderer.py}` |
| three_d_glasses | `src/heart/display/renderers/three_d_glasses.py` | `three_d_glasses/{provider.py,state.py,renderer.py}` |
| three_fractal | `src/heart/display/renderers/three_fractal.py` | `three_fractal/{provider.py,state.py,renderer.py}` |
| tixyland | `src/heart/display/renderers/tixyland.py` | `tixyland/{provider.py,state.py,renderer.py}` |
| yolisten | `src/heart/display/renderers/yolisten.py` | `yolisten/{provider.py,state.py,renderer.py}` |

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early signal |
| --- | --- | --- | --- | --- |
| Subscription leaks when refactors forget to dispose observables | Medium | Medium | Require `reset` to dispose subscriptions and document pattern in providers | Increasing memory use or duplicated state updates after renderer swap |
| Behavioural drift because providers mis-handle timing compared to previous inline logic | Medium | High | Capture timing assumptions before refactor; add smoke tests comparing frame counts or key outputs | Visual tempo changes, missing frames, or stalled animations |
| Asset or font paths broken during package moves | Low | Medium | Keep relative paths stable; add loaders in renderer constructors with error logging | Missing sprites or fallback colours during startup |
| Import cycles when providers and renderers share helper utilities | Low | Low | Centralise shared helpers in package-level modules and keep provider imports lean | Circular import errors at runtime |

### Mitigation checklist

- [ ] Add subscription disposal in each renderer `reset` implementation.
- [ ] Validate timing logic against prior behaviour before deleting original files.
- [ ] Keep asset loaders and constants in package-level modules to minimise churn in renderer code.
- [ ] Run `make format` and targeted tests after each batch to catch regressions early.

## Outcome snapshot

Once completed, every renderer in `src/heart/display/renderers` will expose a coherent provider/state/renderer package mirroring Water and Max BPM. Providers will own peripheral subscriptions, states will remain immutable snapshots, and renderers will focus purely on drawing, making composed playlists and resets reliable across the fleet.
