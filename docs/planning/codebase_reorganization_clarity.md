# Codebase Reorganization for Clarity

## Problem Statement

The current Heart codebase has grown across runtime, renderers, peripherals, and utilities with several modules carrying mixed responsibilities. This increases the cost of onboarding, makes dependency paths less predictable, and complicates changes that should be localized. We need a structured reorganization plan that reduces cross-module coupling, tightens file scope, and documents the intended module boundaries without changing core behaviors.

## Materials

- Repository checkout with tests and tooling enabled.
- Access to existing architecture notes in `docs/code_flow.md` and `docs/library/runtime_systems.md`.
- Recent research notes such as `docs/research/navigation_module_split.md` and `docs/research/env_module_restructure.md`.
- Ability to run `make check` and `make test` locally.

## Opening Abstract

This plan reorganizes core runtime, navigation, renderer, and peripheral modules to clarify ownership and reduce mixed responsibilities. The changes prioritize moving orchestration logic into focused modules, standardizing module entry points, and aligning file layout with existing architecture references. The goal is to make the codebase easier to navigate and change safely, while keeping public behavior intact and documenting new boundaries.

## Success Criteria

| Behavior | Validation Signal | Owner |
| --- | --- | --- |
| Orchestration logic is localized to dedicated modules | Fewer multi-purpose files flagged in code review; module responsibilities documented | Runtime Maintainer |
| Module boundaries are easier to follow | Updated `docs/code_flow.md` references new module layout | Documentation Owner |
| No regressions in core flows | `make test` passes; manual smoke run of CLI entry points | QA / Runtime Maintainer |
| Rendering and peripheral modules remain discoverable | `docs/library` references map to new paths | Renderer Lead |

## Task Breakdown Checklists

### Discovery

- [ ] Inventory multi-responsibility files in `src/heart/runtime`, `src/heart/navigation`, and `src/heart/utilities`.
- [ ] Identify coupling points between runtime orchestration and renderer selection logic (`src/heart/runtime/render_planner.py`, `src/heart/navigation/multi_scene.py`).
- [ ] Map public entry points and CLI command flow (`src/heart/cli/commands/`).
- [ ] Capture current module boundaries in a reference table for later validation.

### Design

- [ ] Propose a target module map that groups orchestration, configuration, and I/O concerns separately.
- [ ] Define stable public APIs for each group, emphasizing interfaces used by CLI and runtime container.
- [ ] Draft file move list with import rewrites and update risks.
- [ ] Outline documentation updates required in `docs/code_flow.md` and `docs/library/`.

### Implementation

- [ ] Split high-responsibility runtime modules into focused helpers (for example, render planning vs. pacing vs. presentation).
- [ ] Consolidate navigation resolution logic into a dedicated folder with clear public entry points.
- [ ] Move peripheral configuration and registry helpers into a single module area to reduce cross-links.
- [ ] Update imports to avoid circular references, using runtime container and provider helpers as documented.
- [ ] Adjust CLI commands to reference the new entry points without behavior changes.
- [ ] Update `docs/code_flow.md` diagram and run `scripts/render_code_flow.py`.

### Validation

- [ ] Run `make check` and confirm formatting and linting remain clean.
- [ ] Run `make test` and record any updated or newly required fixtures.
- [ ] Confirm CLI commands start without import errors (`run`, `game_loop`, `update_driver`).
- [ ] Verify docs references in `docs/library/` and `docs/README.md` remain accurate.

## Narrative Walkthrough

The effort begins with discovery to pinpoint the worst offenders for mixed responsibilities. The initial focus is on runtime orchestration and navigation, since these appear to coordinate multiple concerns. Once the hot spots are identified, the design phase defines the target module map and clarifies public APIs so the refactor has explicit destinations.

Implementation is staged to reduce risk. First, runtime modules are split where responsibilities are most entangled, then navigation and peripheral modules are aligned with that structure. CLI command entry points are updated last so they become the integration check for the reorganized modules. Documentation updates and diagram regeneration follow immediately to keep architecture references synchronized with the code.

Validation is both automated and manual. `make check` and `make test` provide the regression gates, while manual CLI smoke runs confirm that wiring changes did not break runtime entry points. The final review focuses on documentation alignment and the new clarity of module ownership.

## Visual Reference

| Current Area | Issue | Target Boundary |
| --- | --- | --- |
| `src/heart/runtime` | Mixed orchestration, planning, and rendering control | `runtime/orchestration`, `runtime/planning`, `runtime/rendering` |
| `src/heart/navigation` | Resolution and scene management intertwined | `navigation/resolution`, `navigation/scenes` |
| `src/heart/peripheral` | Configuration, registry, and device I/O interleaved | `peripheral/config`, `peripheral/registry`, `peripheral/io` |
| `src/heart/utilities` | Helpers span env parsing, logging, and registry | `utilities/env`, `utilities/logging`, `utilities/registry` |

```text
CLI -> runtime/orchestration -> planning -> rendering -> device output
              |                     |
              v                     v
        navigation/resolution   peripheral/registry
```

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning Signal |
| --- | --- | --- | --- | --- |
| Circular imports after file moves | Medium | High | Stage refactors; add explicit public APIs | Import errors in CLI smoke runs |
| Documentation drift | Medium | Medium | Update docs alongside code moves | Code flow diagram mismatches |
| Hidden runtime coupling | Low | High | Incremental tests and targeted module audits | Unexpected failures in `make test` |
| Over-splitting modules | Medium | Medium | Align with documented boundaries; avoid micro-modules | Review feedback on excessive indirection |

Mitigation Checklist:

- [ ] Keep a staged move list and update imports after each step.
- [ ] Use targeted integration smoke tests after each module group change.
- [ ] Update documentation immediately after structural changes.
- [ ] Validate that public APIs remain stable for CLI and tests.

## Outcome Snapshot

Once complete, runtime orchestration, planning, and rendering live in separate modules with clearly documented boundaries. Navigation resolution is housed in its own folder with a stable public entry point. Peripheral configuration and registry logic are consolidated, and utilities are grouped by concern. Documentation reflects the new layout, and core tests plus CLI entry points run without regressions.

## Related References

- `docs/research/navigation_module_split.md`
- `docs/research/env_module_restructure.md`
- `docs/library/runtime_systems.md`
- `docs/code_flow.md`
