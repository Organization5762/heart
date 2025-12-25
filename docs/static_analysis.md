# Static analysis

## Problem statement

Static analysis helps enforce Heart-specific coding rules that are not covered by
formatters and linters. The project needs a consistent way to detect forbidden
patterns such as `print`-based diagnostics, wildcard imports, module-level
`__all__` exports, and `os.path.join` usage in runtime modules.

## Tooling

Heart uses Semgrep with a repo-local configuration file at `semgrep.yml`. The
current rules focus on Python files under `src/` and align with the guidance in
`AGENTS.md`.

## Usage

- Run the standalone check:
  - `make semgrep`
- Run with the rest of the linting checks:
  - `make check`
- Override the default target set (for example, to scan `tests/` too):
  - `make semgrep SEMGREP_TARGETS="src tests"`

Both targets run `uv run semgrep --config semgrep.yml --error src` by default.

## Rule catalog

| Rule ID | Purpose | Scope |
| --- | --- | --- |
| `heart-no-print` | Ban `print(...)` for runtime diagnostics. | `src/**/*.py` |
| `heart-no-wildcard-import` | Avoid wildcard imports. | `src/**/*.py` |
| `heart-no-module-all` | Avoid module-level `__all__` exports. | `src/**/*.py` |
| `heart-no-os-path-join` | Prefer `pathlib.Path` over `os.path.join`. | `src/**/*.py` |

## Updating the rules

1. Edit `semgrep.yml` to add or refine rules.
1. Keep rule messages aligned with the guidance in `/workspace/heart/AGENTS.md`.
1. Validate new rules with `make semgrep` before committing changes.

## Materials

- `semgrep.yml`
- `make semgrep`
- `make check`
