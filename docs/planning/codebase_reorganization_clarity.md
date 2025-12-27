# Codebase Reorganization for Clarity

## Problem Statement

The `src/heart` package has grown through feature additions, making module boundaries harder to reason about and increasing the cost of navigation, onboarding, and refactoring. Related responsibilities (runtime orchestration, device abstractions, peripheral I/O, and rendering) live in adjacent directories without a consistent layering model, and some modules blend orchestration with data definitions. This plan defines a focused reorganization that clarifies boundaries, reduces cognitive load, and keeps future changes localized.

## Materials

- Hardware: none required for planning; optional target device for runtime smoke checks.
- Software: Python 3.11 environment managed by `uv`, `make`, `rg`, and the existing `Makefile` tooling.
- Data: current module inventory from `src/heart`, documentation index in `docs/planning/README.md`, and relevant runtime diagrams if they exist.

## Opening Abstract

This plan proposes a structured reorganization of the Heart codebase that separates orchestration, data contracts, and device/peripheral implementations into clearer, smaller modules. The work is needed now to keep planned feature work from compounding complexity and to make the runtime pipeline easier to follow during debugging. The intended outcomes are a consistent directory taxonomy, minimal cross-layer imports, and updated documentation that explains the new boundaries.

## Goal & Motivation

The goal is to restructure `src/heart` so that each subsystem has an explicit scope, making the runtime flow and dependency directions obvious to maintainers. The motivation is practical: reduce onboarding time, make it safer to modify rendering and peripheral integrations, and reduce import churn when adding new devices or runtime behaviors.

## Design Overview

The reorganization keeps the public API stable while introducing clearer subsystem boundaries:

- Runtime orchestration remains under `src/heart/runtime` with subpackages for scheduling, rendering, and container wiring.
- Device and peripheral integration code is grouped by responsibility, with shared protocols and configuration models extracted into dedicated modules.
- Renderers and assets remain separate but gain a stricter separation between renderer interfaces and renderer-specific state.
- CLI command modules serve as entrypoints only, delegating work to feature modules without embedding orchestration logic.

## Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Subsystems have clear module boundaries | Dependency graph review shows imports flow from entrypoints to core modules without back-edges | Runtime maintainer |
| Module names reflect responsibilities | Documentation table matches directory structure and reviewers confirm navigation improvements | Docs maintainer |
| Import churn is reduced | `rg`-based audit shows no cross-layer imports outside defined contracts | Codebase maintainer |
| Runtime boot path remains stable | Smoke run of `heart.cli.commands.run` works without path or import errors | Runtime maintainer |

## Task Breakdown

### Discovery

- [ ] Build a module map by subsystem for `src/heart/runtime`, `src/heart/peripheral`, `src/heart/device`, `src/heart/renderers`, and `src/heart/utilities`.
- [ ] Identify modules that mix orchestration with data definitions (for example `src/heart/runtime/game_loop.py` and `src/heart/peripheral/registry.py`).
- [ ] Record cross-layer imports that violate a single-direction dependency model.
- [ ] Review related docs in `docs/planning/` for overlapping plans.

### Implementation

- [ ] Define a target directory taxonomy with module responsibilities and allowed import directions.
- [ ] Extract shared types or configuration models into dedicated modules (for example, split renderer state from renderer execution).
- [ ] Move orchestration helpers into focused subpackages (for example, split runtime scheduling vs. rendering pipeline).
- [ ] Update imports to use new module paths, keeping public APIs stable.
- [ ] Update CLI commands in `src/heart/cli/commands/` to call into refactored modules only.
- [ ] Add or update module-level docstrings for new boundaries and responsibilities.

### Validation

- [ ] Run `make format` and `make check` to ensure formatting and static checks are clean.
- [ ] Run `make test` with focus on runtime integration tests.
- [ ] Perform a smoke run of the runtime entrypoint and confirm renderer selection still works.
- [ ] Update documentation references and ensure `docs/planning/README.md` indexes the plan.

## Narrative Walkthrough

The Discovery phase builds a concrete understanding of where responsibilities currently overlap. The module map enables a dependency audit that highlights the specific files to split or relocate. This reduces the risk of broad, unfocused refactors by keeping the scope tied to measurable issues like cross-layer imports or files that blend orchestration and data.

Implementation begins by defining the target taxonomy, since it guides every move and import update. Moves should be done in small batches per subsystem to reduce the blast radius and keep runtime behavior stable. Shared types and configuration models should be extracted first, because they reduce cyclic imports and clarify the boundary between data definitions and runtime behavior.

Validation ties back to the success criteria. Formatting and checks confirm the plan does not introduce style regressions. Runtime smoke checks confirm that the entrypoints still resolve and that the renderer registry and peripheral registry load without errors. Documentation updates ensure that the plan is visible and that future contributors understand the new layout.

## Visual Reference

The following diagram sketches the intended dependency flow after reorganization:

```text
CLI Commands
  |
  v
Runtime Orchestration ---> Rendering Pipeline ---> Renderers/Assets
  |
  v
Peripheral Runtime -----> Peripheral Providers ----> Device Integrations
  |
  v
Utilities/Shared Types (no reverse imports)
```

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early warning signal |
| --- | --- | --- | --- | --- |
| Hidden import cycles surface during moves | Medium | High | Extract shared types early and enforce one-way imports | Import errors or failing tests after move |
| Runtime boot path breaks | Medium | High | Keep CLI entrypoints stable and update them last | CLI smoke run fails |
| Documentation lags behind changes | Low | Medium | Update docs alongside module moves | Discrepancies in module maps |
| Peripheral integrations regress | Low | High | Validate with targeted runtime smoke checks and stubbed tests | Runtime failure in peripheral loading |

Mitigation checklist:

- [ ] Maintain a running list of updated import paths during refactors.
- [ ] Validate each move with a quick runtime import test.
- [ ] Update docs in the same PR as code moves.
- [ ] Keep a fallback branch or tag for quick diff comparison.

## Outcome Snapshot

After completion, the codebase presents a clear, layered structure with minimal cross-layer imports and focused modules. A contributor can locate runtime orchestration, rendering concerns, and device/peripheral integrations quickly, and documentation reflects the new module boundaries. Runtime entrypoints remain unchanged, and tests confirm that the reorganization does not alter behavior.
