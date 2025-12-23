# Sync harness dry-run change detection

## Summary

The sync harness in `sync.sh` can now run a dry-run pass to detect whether any
files would transfer. When `--skip-noop` (or `SYNC_SKIP_NOOP`) is enabled, the
harness skips hooks and rsync when the dry-run reports no changes.

## Materials

- `sync.sh`
- `docs/sync_harness.md`

## Notes

- The dry-run uses `rsync --itemize-changes` so only real deltas produce output.
- The change detection runs before hooks to prevent unnecessary build or test
  work on no-op sync cycles.
