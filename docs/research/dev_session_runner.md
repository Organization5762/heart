# Developer Session Runner Research Note

## Problem Statement

Developers need a faster iteration loop when editing runtime code because manual restarts of the
`totem run` process slow feedback and make repeated testing tedious.

## Materials

- Python 3.11+ with the Heart runtime installed.
- `uv` for running repository tooling.
- Access to the repository source tree under `src/` and related runtime folders.

## Sources Consulted

- `scripts/devex_session.py` for the restartable runtime loop and watch logic.
- `Makefile` for the `dev-session` entry point.
- `docs/books/development_workflow.md` for usage and operational guidance.

## Findings

- A restartable session loop can reuse the existing `totem run` CLI without modifying runtime
  orchestration in `src/heart/loop.py`.
- Polling-based file watching is sufficient for the runtime folders in this repository and avoids
  adding new dependencies.
- The session runner can set `HEART_RENDER_VARIANT` per run without changing configuration modules.

## Follow-Up Ideas

- Add a renderer preset flag that maps to frequently used development configurations.
- Surface a summary of watched file changes in the session output to shorten debugging time.
