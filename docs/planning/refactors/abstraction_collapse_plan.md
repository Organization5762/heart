# Abstraction Collapse Refactor Plan

## Problem Statement

The Heart codebase has accumulated abstraction layers that may no longer deliver value, create indirection without clear benefit, or remain as vestigial scaffolding after previous refactors. This makes navigation harder, slows onboarding, and increases the cost of changes because the real data flow is spread across thin wrappers. We need a focused, documented plan to identify which abstractions can be safely collapsed while preserving intentional structures (notably the provider/state/renderer consistency used for communication).

## Materials

- Local repository checkout with `make`, `uv`, and Python environment tooling available.
- Access to `src/heart/` modules, especially `peripheral`, `runtime`, and `renderers` packages.
- Ability to run `make format` and `make test` for validation.
- Team knowledge of existing architecture decisions and feature owners for review.

## Opening Abstract

This plan defines a structured audit and refactor process to collapse unneeded or over-engineered abstractions in the Heart codebase. The goal is to remove thin wrappers and vestigial indirection while retaining intentional structural patterns (e.g., provider/state/renderer modularization for consistency in communication). The approach emphasizes discovery, explicit criteria, incremental refactors, and validation so the system remains stable while technical debt is reduced.

## Success Criteria

| Target behavior | Validation signal | Owner |
| --- | --- | --- |
| Abstraction candidates are inventoried with clear evidence | Published inventory table in plan updates | Tech lead |
| Only low-value indirection is removed; architectural patterns are preserved | Review checklist confirms provider/state/renderer pattern untouched | Review group |
| Simplified call graph in targeted subsystems | Updated diagram shows fewer layers, fewer indirections | Refactor owner |
| No functional regressions | `make test` passes and key runtime paths exercised | QA owner |
| Documentation captures rationale and outcome | Plan updated with outcomes and links to PRs | Doc owner |

## Task Breakdown Checklists

### Discovery

- [ ] Build a list of abstractions with file paths, owners, and call sites.
- [ ] Tag each candidate with a collapse reason (thin wrapper, duplicate, vestigial, indirect configuration).
- [ ] Confirm architectural patterns to preserve (provider/state/renderer, standardized renderer packages).
- [ ] Note constraints or contracts that cannot change (public APIs, firmware interface expectations).

### Implementation

- [ ] Choose a small batch of candidates with minimal coupling.
- [ ] Draft refactor steps: inline or merge, delete wrappers, update imports, ensure logging consistency.
- [ ] Preserve intentional patterns (do not collapse provider/state/renderer modules).
- [ ] Document before/after dependency graph for each batch.

### Validation

- [ ] Run `make format` to enforce style.
- [ ] Run `make test` and any targeted scenario checks.
- [ ] Verify runtime entrypoints still boot with expected peripheral and renderer setup.
- [ ] Capture regression notes and update plan outcomes.

## Narrative Walkthrough

The refactor begins with a discovery pass to build a concrete inventory of abstractions, anchored by file paths and call sites. Each candidate is tagged with a rationale for collapse, such as being a single-call-site wrapper or a registry with no configuration variability. The discovery phase also marks invariants that should remain, especially the provider/state/renderer structure used for clear communication and consistent module layout.

The implementation phase proceeds in small batches, starting with the least risky candidates. The refactor steps favor direct, explicit dependencies in the fewest files possible. Each batch includes a before/after dependency mapping so reviewers can verify the simplified architecture. Any adjustments must avoid removing the provider/state/renderer conventions or the modular package boundaries that enable consistent communication across renderers.

Validation closes each batch by enforcing formatting, running the test suite, and performing quick runtime checks. If regressions appear, the plan calls for backing out or isolating the changes and recording the failure conditions to improve the next batch.

## Visual Reference

### Candidate Abstraction Flow (Example)

| Layer | Example Module | Notes |
| --- | --- | --- |
| Caller | `src/heart/peripheral/core/manager.py` | Creates and delegates to `PeripheralStreams`. |
| Wrapper | `src/heart/peripheral/core/streams.py` | Builds Rx streams for peripherals. |
| Implementation | `src/heart/peripheral/...` | Actual peripheral event sources. |

```
[PeripheralManager] -> [PeripheralStreams] -> [Peripheral.observe]
         |                       |
         | (candidate collapse)  | (keep event flow intact)
```

The diagram illustrates how thin wrapper layers may be removed while preserving the underlying data flow and event semantics.

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early warning signal |
| --- | --- | --- | --- | --- |
| Hidden coupling makes collapse unsafe | Medium | High | Require call-site inventory and owner signoff | Unexpected runtime errors or missing events |
| Removing an abstraction breaks implicit contracts | Low | High | Document contracts and run targeted tests | Failed end-to-end or integration tests |
| Architectural consistency degraded | Low | Medium | Explicitly preserve provider/state/renderer structure | Reviewer feedback on structure drift |
| Refactor scope creeps beyond plan | Medium | Medium | Batch small changes and gate each batch | PRs grow beyond single subsystem |

### Mitigation Checklist

- [ ] Confirm each candidate has a single or narrow call-site set.
- [ ] Validate that provider/state/renderer package structure is untouched.
- [ ] Record contract expectations for each candidate before edits.
- [ ] Add small regression tests when contracts are clarified.

## Outcome Snapshot

After the plan is executed, the codebase should show fewer redundant wrappers and a clearer call graph in targeted subsystems. The provider/state/renderer structure remains intact and continues to convey communication boundaries. All removed abstractions are documented with rationale, and each refactor batch links to its PR and validation results. The system remains functionally stable, with simplified dependency paths and easier navigation for contributors.
