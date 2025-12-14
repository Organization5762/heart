# Problem Statement

Pixel renderers previously co-located in `src/heart/display/renderers/pixels.py` now
live in the `src/heart/display/renderers/pixels/` package with dedicated provider,
state, and renderer modules. The follow-up work is to validate the new structure,
ensure configuration imports stay stable, and capture any missing smoke tests or
visual samples.

# Materials

- Python 3.12 within the repository's `uv`-managed environment.
- `pygame` for renderer warm-up and smoke checks.
- Familiarity with `AtomicBaseRenderer` patterns in `src/heart/display/renderers/__init__.py`.
- Existing pixel playlists defined in configuration modules.

# Opening Abstract

Border, Rain, Slinky, and RandomPixel are now packaged under
`src/heart/display/renderers/pixels/` with provider/state/renderer splits. The
remaining tasks focus on confirming that external imports still resolve, that
state updates proceed deterministically across resets, and that documentation
reflects the new layout. The checklist below emphasises validation over further
refactors.

# Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Pixel renderers operate from `pixels/{provider.py,state.py,renderer.py}` without runtime regressions. | Smoke runs confirm animations match prior behaviour. | Display team |
| Configuration modules import the package path without patching. | `make test` and manual import checks succeed. | Display team |
| Documentation acknowledges the new package layout. | Planning and migration notes cite `pixels/renderer.py`. | Documentation lead |
| Basic smoke coverage exists for Border, Rain, and Slinky. | Test stubs or manual runs verify initialization and frame progression. | Display team |

# Task Breakdown Checklists

## Discovery

- [x] Verify the new `pixels/` package layout and module boundaries.
- [x] Confirm Border, Rain, and Slinky initialise via provider/state creation.
- [ ] Capture baseline visuals for comparison during smoke checks.

## Implementation

- [x] Update configuration imports to target `heart.display.renderers.pixels`.
- [x] Remove legacy `pixels.py` module after package creation.
- [ ] Add optional smoke tests for Border, Rain, and Slinky initialisation and frame stepping.
- [ ] Capture screenshots or short clips to confirm visual parity post-refactor.

## Validation

- [ ] Run `make test` to ensure configuration imports remain valid.
- [ ] Execute manual smoke runs for each pixel renderer and compare against baseline visuals.
- [x] Ensure documentation points to the new package paths.

# Narrative Walkthrough

With the provider/state/renderer split in place, the priority shifts to
validation. Configuration modules already import from
`heart.display.renderers.pixels`, so automated and manual checks should confirm
those imports still resolve after the module removal. Light smoke tests can
instantiate each renderer, step the provider-driven state forward using the
clock, and verify that frames progress without mutating shared attributes. Any
visual drift observed during manual runs should be captured alongside the state
that triggered it for easier debugging.

# Visual Reference

| Renderer | Provider responsibilities | State fields | Renderer focus |
| --- | --- | --- | --- |
| Border | Seed and update the border color. | `color` | Draw rectangular outline on the tiled surface. |
| Rain | Advance drop origin and vertical position on each tick. | `starting_point`, `current_y` | Plot faded vertical streaks and respawn at bounds. |
| Slinky | Step the falling anchor and dimming profile. | `starting_point`, `current_y` | Render triangular brightness profile with mirrored tails. |

# Risk Analysis

| Risk | Probability | Impact | Mitigation | Early signals |
| --- | --- | --- | --- | --- |
| Configuration imports still reference the removed `pixels.py` file. | Medium | High | Grep configuration modules and run smoke imports after the refactor. | ImportError during test startup. |
| Frame timing differs from the pre-refactor behaviour. | Medium | Medium | Compare baseline recordings and adjust provider timing to mirror prior `clock.get_time()` usage. | Animations appear faster or slower during smoke runs. |
| Missing smoke coverage leaves regressions unnoticed. | Medium | Medium | Add minimal tests that initialise each renderer and tick the provider state. | Animations fail silently when composed into playlists. |
