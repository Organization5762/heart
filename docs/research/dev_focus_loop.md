# Research Note: Developer Focus Loop

## Technical Problem

Iteration speed slows when developers must run repository-wide formatting and tests for small changes. The focus loop aims to keep feedback localized to the files that changed while still enforcing formatting rules and providing targeted test coverage.

## Materials

- `scripts/devex_focus.py` for change detection and command orchestration.
- `Makefile` targets that expose the workflow.
- `docs/dev_focus_loop.md` for user-facing usage guidance.

## Findings

- Change detection leverages `git diff` and `git ls-files` so formatting and test selection stay close to modified files.
- The workflow separates formatting and testing into explicit steps so developers can choose between `check` and `format` modes.
- Watch mode uses polling to rerun the loop when files change, providing continuous feedback during active development.

## Source References

- `scripts/devex_focus.py` (focus loop implementation)
- `Makefile` (focus and focus-watch targets)
- `docs/dev_focus_loop.md` (concept and usage)
- `docs/developer_experience.md` (developer experience summary update)
