# Synchronize a Build or Harness Workspace

This guide explains how to use `sync.sh` to keep a local workspace aligned with a remote
host while optionally running build or harness steps before and after each sync.

## Materials

- `rsync` installed locally.
- Optional watcher:
  - `fswatch` (macOS, Linux), or
  - `inotifywait` (Linux via `inotify-tools`).
- Optional `spellcheck` command available on `PATH`.
- Optional `sshpass` when using `REMOTE_PASS` for password-based SSH.

## Quick start

Run a one-time sync of the current directory:

```bash
./sync.sh --once
```

Sync with a build step that runs before each upload:

```bash
./sync.sh --pre-sync "make build" --once
```

## Configure build and harness hooks

Use pre- and post-sync hooks to add build or verification steps without editing the
script. Hooks run from the source directory.

| Option | Environment variable | Purpose |
| --- | --- | --- |
| `--pre-sync CMD` | `SYNC_PRE_SYNC_CMD` | Run a command before each sync. |
| `--post-sync CMD` | `SYNC_POST_SYNC_CMD` | Run a command after each sync. |

Example with environment variables:

```bash
export SYNC_PRE_SYNC_CMD="make format"
export SYNC_POST_SYNC_CMD="make test"
./sync.sh --once
```

## Notes

- Use `--skip-spellcheck` if the `spellcheck` tool is not installed.
- Use `--dry-run` to preview changes before syncing.
- If a hook fails, the script exits with the hook's non-zero status.
