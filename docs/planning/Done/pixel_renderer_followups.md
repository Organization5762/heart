# Problem Statement

The `src/heart/renderers/pixels.py` module still contains multiple renderers that share state and rendering logic inside a single file. Only the `RandomPixel` renderer has been split into a provider, state, and renderer trio. `Border`, `Rain`, and `Slinky` keep their state classes and rendering code interleaved, which makes it harder to adopt the observable-driven patterns used by `water_title_screen` and to test state changes independently. The goal is to carve those remaining renderers into isolated packages with clear ownership for state evolution and drawing.

# Materials

- Python 3.12 with the repository's `uv`-managed environment.
- Access to `pygame` for surface operations during renderer warm-up.
- Familiarity with `StatefulBaseRenderer` and `ObservableProvider` in `src/heart/renderers/__init__.py`.
- Editor capable of handling nested package refactors.
- Optional: `scripts/render_code_flow.py` if any flow diagrams need regeneration after structural changes.

# Opening Abstract

The pixel renderer family is moving toward the provider/state/renderer split already proven in `water_title_screen`. `RandomPixel` now follows that model, but `Border`, `Rain`, and `Slinky` still couple their state creation and draw routines. This plan enumerates tasks to refactor each remaining renderer so their state progression is observable and testable. Completing the checklist will leave the module with consistent boundaries: providers own observable state, states are immutable dataclasses, and renderers concentrate on draw logic.

# Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Each remaining pixel renderer lives in its own package with `provider.py`, `state.py`, and `renderer.py`. | Directory structure under `src/heart/renderers/` shows `border/`, `rain/`, and `slinky/` folders with the three files. | Display team |
| Renderer state updates are driven by observables rather than ad-hoc `update_state` calls. | Unit or smoke tests can subscribe to providers and receive deterministic state transitions. | Display team |
| API consumers import renderers from their dedicated packages without breaking existing configurations. | `make test` passes and configuration modules import the new paths. | Display team |
| Documentation reflects the new structure and rationale. | Updated planning and follow-up notes exist in `docs/planning/` with diagrams or tables. | Documentation lead |

# Task Breakdown Checklists

## Discovery

- [ ] Review how `RandomPixel` now wires `RandomPixelStateProvider` into `StatefulBaseRenderer` for reference.
- [ ] Map current state mutation points for `Border`, `Rain`, and `Slinky` (e.g., `_create_initial_state`, `_change_starting_point`).
- [ ] Identify any shared helpers in `pixels.py` that need to be copied or centralised to avoid circular imports.

## Implementation

- [ ] **Border renderer package**
  - [ ] Create `src/heart/renderers/border/state.py` with an immutable `BorderState` dataclass.
  - [ ] Implement `BorderStateProvider` that exposes an observable stream seeded with the initial color and supports color updates.
  - [ ] Move draw logic into `src/heart/renderers/border/renderer.py`, subclassing `StatefulBaseRenderer`.
  - [ ] Update configuration files to import `Border` from the new package and remove legacy definitions from `pixels.py`.
- [ ] **Rain renderer package**
  - [ ] Define `RainState` in `state.py` with explicit fields for drop origin and position.
  - [ ] Build a provider that ticks rain position forward on `game_tick` or `clock` observables to mirror the existing progression rules.
  - [ ] Port rendering into `renderer.py`, ensuring brightness gradients are applied using immutable state snapshots.
  - [ ] Replace legacy imports and delete the old `Rain` class from `pixels.py`.
- [ ] **Slinky renderer package**
  - [ ] Capture `SlinkyState` in `state.py`, including parameters for starting point, trajectory, and color fading.
  - [ ] Create a provider that advances the slinky motion deterministically and emits new states at each tick.
  - [ ] Move rendering into `renderer.py`, using provider-fed state for position and dimming instead of mutating in place.
  - [ ] Update configurations and clean up `pixels.py` once the new package is wired.

## Validation

- [ ] Add or update smoke tests that instantiate each renderer via its provider to ensure `initialize` wires subscriptions correctly.
- [ ] Run `make test` to confirm configuration imports resolve and rendering loops execute without mutation errors.
- [ ] Capture a short GIF or screenshot of each refactored renderer once available to verify visual parity.
- [ ] Review documentation to ensure the rationale and new folder layout are linked from relevant docs.

# Narrative Walkthrough

Begin with the Border renderer because it has the fewest moving parts. Extract its `BorderState` and initial color handling into a provider that emits a `BehaviorSubject`, mirroring the new `RandomPixel` provider. This establishes a pattern for observable state streams that the renderer subscribes to during initialization. Once Border works, move to Rain, which introduces time-based state. The provider should listen to `PeripheralManager.game_tick` and `clock` observables (as `water_title_screen` does) to update drop positions deterministically. Rendering then becomes a pure function of the immutable `RainState` emitted by the provider.

Finally, refactor Slinky, which combines motion and dimming. Its provider can build on Rain's pattern but may also need to incorporate phase tracking to vary brightness over the slinky length. After each renderer is split, delete the legacy classes from `pixels.py` and migrate configuration imports to the new package paths. Keeping the imports up to date prevents dead code from lingering and ensures all scenes exercise the refactored structure.

# Visual Reference

| Renderer | Provider responsibilities | State fields | Renderer focus |
| --- | --- | --- | --- |
| Border | Seed and broadcast color changes. | `color` | Draw rectangular outline across the tiled surface. |
| Rain | Emit updated drop origin and vertical position on each tick. | `starting_point`, `current_y`, drop length constants | Plot faded vertical streaks while respawning at bounds. |
| Slinky | Advance slinky head position and dimming phase. | `starting_point`, `current_y`, optional phase counter | Render triangular brightness profile with mirrored tails. |

# Risk Analysis

| Risk | Probability | Impact | Mitigation | Early signals |
| --- | --- | --- | --- | --- |
| Providers drift from current frame timing, changing animation speed. | Medium | Medium | Use `Clock.get_time()` in providers to mirror existing step sizes and write assertions around delta handling. | Visual playback speeds differ from baseline recordings. |
| Configuration imports miss updated paths and fail at runtime. | Medium | High | Update all `pixels` imports during refactor and add a smoke test that loads each configuration. | CI failures citing `ImportError` or missing renderer classes. |
| Observable subscriptions leak and continue emitting after renderer disposal. | Low | Medium | Mirror the `water_title_screen` pattern of shared observables and ensure subscriptions tie to renderer lifetime. | Increasing memory use or duplicate frames during scene transitions. |

## Mitigation Checklist

- [ ] Add unit tests that pin expected state transitions for each provider using synthetic clock inputs.
- [ ] Verify renderer initialization subscribes exactly once and cleans up between scenes.
- [ ] Validate import paths in every configuration that previously referenced `pixels.RandomPixel`, `Border`, `Rain`, or `Slinky`.
- [ ] Capture before/after frame timing metrics to catch unintended performance regressions.

# Outcome Snapshot

After completing the tasks, each pixel renderer resides in its own provider/state/renderer package, mirroring the `water_title_screen` layout. Providers own immutable dataclass states, renderers focus solely on drawing, and configurations import from stable package paths. The refactor leaves the pixel family ready for further observable-driven features without the coupling that currently lives in `pixels.py`.
