# Development Workflow

## Problem Statement

Local iteration on Heart can be slow when changes require full reformatting, full test runs, or
manual restarts of `totem`. This workflow keeps feedback tight while preserving enough context
for troubleshooting.

## Materials

- Python 3.11+ environment with Heart installed.
- `uv` for running repository tooling.
- `git` for change detection (recommended).
- SDL-compatible display stack if you want to preview pygame output.

## Daily Loop

Use the focus loop for change-aware formatting and tests:

```bash
make focus
```

Watch for changes and rerun automatically:

```bash
make focus-watch
```

Run checks without applying formatting fixes:

```bash
uv run python scripts/devex_focus.py --mode check
```

## Restartable Runtime Session

Keep a local `totem run` loop active and restart it on file changes:

```bash
make dev-session
```

Override configuration or rendering variants:

```bash
uv run python scripts/devex_session.py --configuration lib_2025 --render-variant parallel
```

Disable file watching when you just want a single run:

```bash
uv run python scripts/devex_session.py --no-watch
```

## Developer Experience Snapshot

Capture a structured snapshot of the environment and repo state for troubleshooting:

```bash
make doctor
```

Capture the same report as JSON:

```bash
uv run python scripts/devex_snapshot.py --format json --output devex_snapshot.json
```

## Notes

- The focus loop targets changed Python and documentation files and falls back to
  last-failed tests when available.
- The session runner watches `src/`, `drivers/`, `experimental/`, and `scripts/` by default.
- When reproducing bugs, attach the snapshot output and the command you ran.
