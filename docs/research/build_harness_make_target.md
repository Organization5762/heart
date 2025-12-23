# Build harness: Makefile build target

## Summary

The build harness referenced `make build` in documentation, but the Makefile did not provide
that target. This left build hooks in `sync.sh` without a default build action.

## Changes

- Added a `build` target to the Makefile that runs `uv build` and supports `BUILD_ARGS`.
- Documented the `make build` behaviour in the sync harness guide so hook usage is explicit.

## Materials

- `Makefile`
- `docs/sync_harness.md`
