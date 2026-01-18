# Visual regression phash pipeline

## Problem Statement

The renderer test suite currently relies on hand-crafted expectations and a small set of perceptual hash checks. We lack a systematic way to prevent pixel-level regressions across programs, state transitions, and time-driven rendering changes. The goal is to define a repeatable pipeline that captures baseline visuals per program state and validates them with perceptual hashes so regressions are detected without brittle pixel-perfect comparisons.

## Materials

- Hardware: LED panel or simulator capable of running Heart renderers.
- Software: `imagehash`, `Pillow`, `pytest`, `uv`, `make`.
- Code: `src/heart/display/recorder.py`, `src/heart/display/regression.py`, `tests/display/test_screen_recorder.py`, `src/heart/runtime/game_loop/`, `src/heart/programs/`.
- Data: Baseline frame assets stored under `docs/research/visual_regression/`.

## Opening abstract

This plan introduces a structured visual regression harness that records frames for deterministic program states, hashes them with perceptual hashing, and compares results against curated baselines. It focuses on two axes: program-specific state snapshots (menus, idle states, static scenes) and renderer evolution over time (clock ticks, animation frames, input-driven state changes). The output is a consistent regression signal with documented baselines, reproducible capture scripts, and automated tests to guard against regressions.

## Success criteria table

| Behaviour | Validation signal | Owner |
| --- | --- | --- |
| Baseline captures exist for top-level programs and representative state snapshots. | Baseline assets stored in `docs/research/visual_regression/baselines/` with metadata JSON. | Runtime maintainer |
| Perceptual hash comparisons for each baseline remain within configured thresholds. | Pytest suite passes with hash distance within limits. | Runtime maintainer |
| State transitions (tick/clock/input) are covered for at least one animated renderer. | Test captures include multiple frames per state transition with hash checks. | Renderers owner |
| Capture tooling replays deterministic scenes across environments. | `scripts/visual_regression_capture.py` outputs consistent hashes with fixed seeds. | Developer experience |
| Documentation outlines how to update baselines and interpret failures. | `docs/research/visual_regression/README.md` exists with step-by-step guide. | Documentation owner |

## Task breakdown checklists

### Discovery

- [ ] Inventory existing renderer tests and identify deterministic renderers suitable for baselines (`tests/display/test_screen_recorder.py`).
- [ ] Catalogue program states that must never regress (startup, idle, menu, core playlists).
- [ ] Document the sources of nondeterminism (random seeds, time-based animations, input jitter).
- [ ] Identify the minimal metadata required to replay a state (program name, renderer list, seed, tick count, input snapshot).

### Implementation

- [ ] Add a capture helper that returns raw frames for program render sequences (`src/heart/display/recorder.py`).
- [ ] Add a perceptual hash helper module for comparisons and reporting (`src/heart/display/regression.py`).
- [ ] Create a capture script (`scripts/visual_regression_capture.py`) that runs deterministic program states and stores baseline frames plus metadata.
- [ ] Add tests under `tests/display/` that load baselines and assert perceptual hash distances stay within thresholds.
- [ ] Store baseline artefacts and metadata under `docs/research/visual_regression/` with clear update instructions.

### Validation

- [ ] Run `make format` to ensure formatting and documentation rules pass.
- [ ] Run `make test` and confirm all visual regression tests pass.
- [ ] Validate capture script output against stored baselines on two environments.
- [ ] Record validation steps in the plan’s outcome snapshot and update `docs/research/visual_regression/README.md`.

## Narrative walkthrough

Discovery starts by grounding the scope in existing ScreenRecorder coverage and identifying renderers that already support deterministic output. The next step is to map high-value program states and decide the minimum metadata required to replay them. That metadata guides the design of the capture script, which acts as the single pipeline for baseline generation. Implementation adds reusable capture and hash utilities so tests can pull from a shared source instead of re-implementing logic. Validation confirms that the pipeline produces stable hashes and documents how to update baselines when intentional visual changes land. These phases align so that capture tooling and tests are built from the same primitives, minimizing drift between baseline generation and regression checks.

## Visual reference

| Stage | Input | Output | Owner |
| --- | --- | --- | --- |
| Capture | Program + renderer state + seed + tick count | Baseline frame PNGs + metadata JSON | Developer experience |
| Hash | Baseline frames + observed frames | Hash distances + comparison report | Runtime maintainer |
| Validate | Hash report + threshold config | Pytest pass/fail | QA |

```
Program State -> ScreenRecorder.capture_frames -> Baseline Frames
Baseline Frames -> phash -> Expected Hashes
Observed Frames -> phash -> Observed Hashes
Observed vs Expected -> Hash Distance -> Test Assertion
```

## Risk analysis

| Risk | Probability | Impact | Mitigation | Early warning signal |
| --- | --- | --- | --- | --- |
| Baselines drift due to nondeterminism in renderer state. | Medium | High | Enforce fixed seeds and serialized input snapshots; flag nondeterministic renderers. | Hash distances fluctuate across reruns. |
| Hash thresholds too lax or too strict. | Medium | Medium | Calibrate thresholds per renderer and document rationale; add visual diff review. | Excessive false positives or missed regressions. |
| Baseline assets become stale without documentation. | Medium | Medium | Provide update script and documentation in `docs/research/visual_regression/README.md`. | Tests fail without clear remediation steps. |
| Capture script adds heavy runtime overhead. | Low | Medium | Allow selective capture subsets and cache state metadata. | Capture runs exceed time budget. |

- [ ] Add deterministic seeding per renderer in capture script.
- [ ] Define per-renderer hash thresholds with defaults in metadata.
- [ ] Provide a baseline update guide with examples.
- [ ] Gate heavy captures behind flags for local runs.

## Outcome snapshot

Once this plan lands, Heart has a reproducible visual regression pipeline with documented baselines, a capture script, and tests that validate program state visuals via perceptual hashing. Developers can update baselines intentionally using a single script, and reviewers can interpret regression failures using stored metadata and hashes. The system protects against pixel-level regressions across program states and time-driven rendering changes without requiring brittle pixel-by-pixel comparisons.
