# Sync harness locking for overlapping triggers

## Summary

The sync harness in `sync.sh` now serializes sync runs with a lock keyed to the
source and destination paths. When multiple filesystem events fire in quick
succession, the lock prevents overlapping builds or rsync transfers and logs a
skip instead.

## Materials

- `sync.sh`

## Notes

- `flock` is used when available to hold a per-sync lock file.
- When `flock` is unavailable, the script falls back to a directory-based lock.
