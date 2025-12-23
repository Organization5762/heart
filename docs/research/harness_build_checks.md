# Harness and build checks research note

## Problem statement

Local builds and sync workflows depend on a small set of command-line tools and
expected repository files. The project did not surface missing prerequisites or
version mismatches early, which made harness setup and packaging builds harder to
diagnose.

## Observations

- The harness check script verifies only a subset of required tools and does not
  validate the Python version needed by the project.
- Build and format steps use `uv` tooling, so `uvx` is a practical dependency
  even when `uv` is present.
- The build pipeline assumes `uv.lock` exists, but that file may be absent on a
  fresh checkout.

## Proposed adjustments

- Extend `scripts/check_harness.sh` to validate Python >= 3.11, verify `uvx`, and
  report missing repository artifacts that the harness expects.
- Tie `make build` to the harness check so packaging failures appear before
  running `uv build`.

## Source locations reviewed

- `scripts/check_harness.sh`
- `Makefile`
- `sync.sh`
- `pyproject.toml`

## Materials

- Shell environment with `bash`
- `python3` (>= 3.11)
- `uv`/`uvx`
- `rsync`
