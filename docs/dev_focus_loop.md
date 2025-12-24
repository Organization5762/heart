# Developer Focus Loop

## Problem Statement

Running formatting, linting, and tests across the entire repository slows iteration, especially when only a handful of files have changed. The developer focus loop narrows feedback to the files touched in the working tree while still keeping formatting and test feedback close to the change.

## Materials

- Python 3.11+ environment with Heart installed.
- `uv` for running repository tooling.
- `git` for detecting change sets (recommended).

## Concept

The developer focus loop is a change-aware workflow that:

- Detects modified or newly-added files with `git`.
- Runs formatting or lint checks only on changed Python and documentation files.
- Runs focused tests based on changed tests or last-failed results.
- Optionally watches for file changes and reruns automatically.

## Usage

Run the focus loop once (formatting changed files and running relevant tests):

```bash
make focus
```

Run checks without applying formatting fixes:

```bash
uv run python scripts/devex_focus.py --mode check
```

Watch for changes and rerun the loop automatically:

```bash
make focus-watch
```

Adjust the polling interval when watching:

```bash
uv run python scripts/devex_focus.py --watch --poll-interval 1.0
```

Force all tests (for a heavier validation pass):

```bash
uv run python scripts/devex_focus.py --test-scope all
```

## Notes

- When no changed tests are detected, the focus loop will run last-failed tests if available. Run `make test` for full coverage when needed.
- The loop polls for file changes in `src/`, `tests/`, `docs/`, and `scripts/` when watch mode is enabled.
- The loop falls back to scanning those folders if `git` is unavailable.
