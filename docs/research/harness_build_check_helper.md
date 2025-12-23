______________________________________________________________________

## title: Harness check helper for build tooling

## Summary

This note captures the new harness check helper that validates core tooling for
sync and build workflows before running hooks.

## Changes

- Added `scripts/check_harness.sh` to verify required commands like `uv` and
  `rsync`, report optional helpers, and confirm expected files exist.
- Added a `make check-harness` target to make the helper easy to run from the
  standard build interface.
- Documented the helper in `docs/sync_harness.md` so hook recipes point to a
  real script.

## Materials

- `scripts/check_harness.sh`
- `Makefile`
- `docs/sync_harness.md`
