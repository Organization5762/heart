______________________________________________________________________

## title: Harness config visibility and shared checks

## Summary

This note records harness updates that make sync/build configuration easier to
inspect while keeping common tooling checks in one place.

## Changes

- Centralized shared harness helpers for command and file checks so sync and
  build validation follow the same expectations.
- Added a `--print-config` mode to `sync.sh` so the resolved watcher, hooks, and
  rsync arguments can be reviewed without running a sync.
- Extended the harness check helper to report tool versions and to verify the
  Makefile is present for build workflows.

## Materials

- `scripts/harness_utils.sh`
- `scripts/check_harness.sh`
- `sync.sh`
- `docs/sync_harness.md`
