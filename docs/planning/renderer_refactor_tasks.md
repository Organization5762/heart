# Renderer Refactor Task Set

## Problem Statement

The renderer catalogue mixes monolithic single-file implementations with modular provider/state/renderer packages. This inconsistency slows maintenance, hides shared patterns, and complicates onboarding. We need a repeatable refactor plan so every unrefactored renderer matches the Water/Life-style separation of responsibilities.

## Materials

- Python 3.12 environment with `uv` for dependency resolution and `pygame`, `reactivex`, `numpy`, and linting toolchain (`ruff`, `black`, `isort`, `mdformat`).
- Access to the `heart.display.renderers` package and its existing `StatefulBaseRenderer`/`ObservableProvider` utilities.
- Device simulator or hardware target capable of exercising `DeviceDisplayMode` variants.
- Diagramming support (Mermaid/PlantUML) for quick flow sketches when splitting renderers.

## Opening abstract

We will standardize renderer layout across the codebase by migrating each single-file renderer into a three-part structure (state, provider, renderer). The work reuses the observable-driven update loop adopted by `water_title_screen` and `led_wave_boat`, preserving behaviour while clarifying where data is generated and how it is rendered. Completion leaves the renderer directory predictable and ready for future GPU or peripheral integrations without further churn.

## Success criteria table

| Goal | Signal | Owner |
| --- | --- | --- |
| Every renderer listed below ships as `state.py`, `provider.py`, and `renderer.py` in its own directory | Code review shows packaged structure with matching imports; `make test` passes | Display team |
| State mutation flows rely on providers fed by clock or peripheral streams | Providers pull from `PeripheralManager` and expose observables consumed by `StatefulBaseRenderer` | Display team |
| Behaviour parity preserved | Visual spot-checks and existing tests (where present) still pass; frame timings unchanged within ±5% | QA |
| Documentation updated | `docs/research` entries reference new module paths; README snippets reflect refactored imports | Docs |

## Task breakdown checklists

### Discovery

- [ ] Catalogue runtime dependencies for each renderer (assets, shaders, peripherals) and note any special initialisation hooks.
- [ ] Identify renderers that already use observables to reuse patterns and avoid divergence.
- [ ] Capture current import paths used by downstream modules or docs to plan updates.

### Implementation

- [ ] Create per-renderer directories with `__init__.py`, `state.py`, `provider.py`, and `renderer.py` mirroring the Water/Life layout.
- [ ] Move stateful data classes and per-frame integration math into `state.py`; ensure immutability or safe copying where numpy arrays are involved.
- [ ] Implement providers that subscribe to `PeripheralManager` streams (`clock`, `game_tick`, sensors as needed) and emit updated states.
- [ ] Keep rendering-only logic (blitting, shader invocation, draw calls) inside `renderer.py`, consuming provider-fed state.
- [ ] Update module imports across the repository and docs to reference the new package paths.
- [ ] Add or adjust smoke tests when available to confirm rendering loops run without exceptions.

### Validation

- [ ] Run `make format` and `make test` to confirm style and behaviour.
- [ ] Perform quick visual validation on representative layouts (FULL, MIRRORED, OPENGL) for renderers that support them.
- [ ] Verify peripheral subscriptions unsubscribe cleanly on teardown to avoid leaks during integration tests.

## Renderer-specific tasks

| Renderer | Refactor focus |
| --- | --- |
| `artist.py` | Isolate brush path state and provider-driven tick updates; keep palette interpolation in renderer. |
| `cloth_sail.py` | Extract GL program/shader compilation state; provider supplies timing and wind vectors. |
| `color.py` | Move palette cycling state into provider; renderer handles fill/blit only. |
| `combined_bpm_screen.py` | Capture BPM/state fusion logic in provider tied to peripheral metrics; renderer draws gauges. |
| `flame.py` | Separate numpy-based noise buffers into state; provider advances noise fields per tick. |
| `free_text.py` | Provider supplies text payloads and timing; renderer focuses on layout and blitting. |
| `heart_title_screen.py` | Provider drives animation offsets; renderer paints title assets. |
| `hilbert_curve.py` | Shift curve interpolation data into state/provider; renderer only draws polylines. |
| `image.py` | Provider handles asset loading/rotation state; renderer blits prepared frames. |
| `kirby.py` | Provider manages sprite index/state machine; renderer blits frames. |
| `l_system.py` | Provider advances L-system iterations; renderer converts cached segments to draws. |
| `max_bpm_screen.py` | Provider watches BPM inputs and thresholds; renderer displays metrics. |
| `metadata_screen.py` | Provider aggregates metadata text; renderer formats and displays. |
| `multicolor.py` | Provider cycles colour gradients; renderer handles fills and transitions. |
| `pacman.py` | Provider runs entity positions and random seeds; renderer draws sprites. |
| `pixels.py` | Provider maintains pixel buffer mutations; renderer outputs to surface. |
| `porthole_window.py` | Provider updates window motion state; renderer clips/draws panels. |
| `sliding_image.py` | Provider orchestrates slide timings; renderer applies transforms. |
| `spritesheet.py` | Provider selects frames; renderer blits to layout. |
| `spritesheet_random.py` | Provider randomizes frame selection with tick cadence; renderer draws. |
| `three_d_glasses.py` | Provider manages stereo offset timing; renderer performs compositing. |
| `three_fractal.py` | Provider iterates fractal parameters per tick; renderer maps colour fields. |
| `tixyland.py` | Provider evaluates expressions over time; renderer renders the grid. |
| `yolisten.py` | Provider handles audio/reactive state; renderer visualises amplitude/beat cues. |

## Narrative walkthrough

Each renderer will be lifted into a directory that mirrors the Water/Life blueprint: `state.py` holds immutable simulation data, `provider.py` updates that data on `game_tick` using `PeripheralManager` streams, and `renderer.py` consumes the latest state to draw surfaces. Discovery clarifies dependencies (e.g., shaders for `cloth_sail.py`, asset loaders for `kirby.py`). Implementation proceeds renderer by renderer, ensuring imports redirect to the new packages and that providers expose shared observables. Validation relies on automated formatting/tests plus brief manual spot-checks to confirm frame cadence and visual fidelity have not regressed.

## Visual reference

| Step | Input | Output |
| --- | --- | --- |
| Provider subscription | `game_tick`, `clock`, optional sensors | Stream of renderer-specific state snapshots |
| Renderer draw | State snapshot, pygame surface | Composited frame respecting `DeviceDisplayMode` |
| Tiling/post-processing | Frame + orientation layout | Mirrored/combined output written to window |

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early signal |
| --- | --- | --- | --- | --- |
| Behaviour drift during refactor | Medium | High | Compare frames pre/post where assets allow; keep per-frame math in state methods unchanged | Visual artifacts, timing shifts |
| Observable misuse leading to leaks | Medium | Medium | Use `share()` and unsubscribe hooks; mirror patterns from Water renderer | Rising memory or CPU over time |
| Asset path regressions | Low | Medium | Centralise asset loading in providers and add lightweight smoke tests | Missing sprites or blank frames |
| Performance regressions from extra copying | Medium | Medium | Profile numpy copies; keep arrays contiguous and reuse buffers where safe | FPS drops or GC spikes |

### Mitigation checklist

- [ ] Add unit or smoke tests for providers with deterministic seeds where feasible.
- [ ] Reuse numpy arrays or in-place updates when safe to avoid alloc churn.
- [ ] Document new import paths in README snippets and research notes.
- [ ] Verify unsubscribing/cleanup paths in renderers that manage OpenGL or audio resources.

## Outcome snapshot

When these tasks are complete, every renderer in `heart.display.renderers` will follow a consistent provider/state/renderer structure. Providers will stream deterministic state snapshots tied to `PeripheralManager`, renderers will focus solely on compositing, and documentation will reference stable import paths. The directory will be easier to navigate, onboarding will speed up, and future feature work (sensor-driven visuals, GPU experiments) will slot into the shared scaffold without bespoke rewrites.
