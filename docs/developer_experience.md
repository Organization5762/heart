# Developer Experience Snapshot

## Problem Statement

When development issues surface, teams often lack a consistent snapshot of the environment, tooling, and repository state. This makes it harder to reproduce problems, verify setup drift, or compare local state with CI. The developer experience snapshot provides a single report that captures these details in a repeatable way.

## Materials

- Python 3.11+ environment with the Heart runtime installed.
- `uv` for running the repository tooling.
- `git` for repository metadata (optional but recommended).

## Concept

A developer experience snapshot is a structured report that records:

- Host platform and Python runtime details.
- Tooling versions for `uv` and `git` when present.
- Repository metadata (root, branch, commit, dirty state).
- Active virtual environment paths.

The snapshot is designed to be quick to run and safe to share in issue reports. Text output is human-readable for chat and logs, while JSON output can be attached to tickets or automation.

## Usage

Generate a text snapshot for troubleshooting:

```bash
make doctor
```

Capture the same data in JSON for automation or archival:

```bash
uv run python scripts/devex_snapshot.py --format json --output devex_snapshot.json
```

## Outputs

The default output highlights the platform, tool versions, and repository state. Use JSON output when you need to diff snapshots over time or feed them into other tooling.
