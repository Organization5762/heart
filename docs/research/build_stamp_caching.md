# Build stamp caching for package builds

## Problem statement

Repeated local packaging runs are expensive when the build inputs have not
changed. Developers running `make build` during sync loops or iterative testing
end up paying for redundant `uv build` work.

## Observations

- `make build` currently invokes `uv build` directly, so it has no awareness of
  when packaging inputs are unchanged.
- Build inputs are already well-defined around the source tree and packaging
  metadata, so they can be hashed to determine whether work is needed.

## Proposed adjustment

Introduce a build stamp helper that hashes build inputs and skips `uv build`
when the hash matches the last successful build. Expose environment variables so
teams can force rebuilds or expand the input list for specialized workflows.

## Source locations reviewed

- `Makefile`
- `scripts/build_package.sh`
- `docs/sync_harness.md`

## Materials

- `bash`
- `python` (for hashing files)
- `uv` (packaging)
