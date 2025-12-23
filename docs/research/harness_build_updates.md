______________________________________________________________________

## title: Harness and build updates (sync + Makefile)

## Summary

This note records updates to the developer harness and build helpers so contributors can tune
sync behavior and keep tool installation consistent.

## Changes

- Added `--rsync-arg`/`SYNC_RSYNC_ARGS` support in `sync.sh` so callers can append custom rsync
  flags without editing the script.
- Consolidated Makefile tool installation into a single list so the install harness stays in
  sync with the formatting/linting stack.

## Materials

- `sync.sh`
- `Makefile`
