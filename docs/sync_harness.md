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
- Optional `flock` (or a filesystem that supports directory locks) to prevent overlapping sync runs.

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
| `--pre-sync CMD` | `SYNC_PRE_SYNC_CMD` | Run a command before each sync. Repeat the option to run multiple commands. |
| `--post-sync CMD` | `SYNC_POST_SYNC_CMD` | Run a command after each sync. Repeat the option to run multiple commands. |
| `--skip-noop` | `SYNC_SKIP_NOOP` | Skip hooks and rsync when a dry-run reports no changes. |

Example with environment variables:

```bash
export SYNC_PRE_SYNC_CMD="make format"
export SYNC_POST_SYNC_CMD="make test"
./sync.sh --once
```

Example with multiple hooks:

```bash
./sync.sh --pre-sync "make format" --pre-sync "make build" \
  --post-sync "make test" --post-sync "scripts/check_harness.sh" --once
```

`make build` runs `uv build` through `scripts/build_package.sh`. The wrapper
skips repeated builds when the packaging inputs are unchanged, writing a stamp
under `build/.package_stamp`.

Build helpers:

- `BUILD_ARGS` passes extra arguments to `uv build`.
- `BUILD_HASH_MODE` selects how build inputs are hashed (`content` or `metadata`).
- `BUILD_FORCE=true` forces a build even if the inputs are unchanged.
- `BUILD_PROFILE` selects a named build profile from `scripts/build_profiles.json`.
- `BUILD_PROFILE_FILE` points at a JSON file containing build profile definitions.
- `BUILD_STAMP_PATH` overrides the build stamp location.
- `BUILD_MANIFEST_PATH` writes a JSON summary of the build decision.
- `BUILD_INPUTS` overrides the default inputs (`src`, `pyproject.toml`,
  `README.md`, `uv.lock`) as a space-delimited list.
- `BUILD_INPUTS_FILE` points at a newline-delimited list of build inputs.
- `PYTHON_BIN` chooses the Python interpreter used for hashing and manifests.

## Harness check helper

`scripts/check_harness.sh` verifies the core tooling expected by the sync and
build harness. It confirms required commands like `uv` and `rsync` exist, reports
optional helpers (for example `spellcheck`), checks that uv tools listed in
`scripts/harness_tools.txt` are installed (parsed via
`scripts/list_harness_tools.sh`), and flags missing files such as `.syncignore`.

## Notes

- Use `--skip-spellcheck` if the `spellcheck` tool is not installed.
- Use `--dry-run` to preview changes before syncing.
- Use `--skip-noop` to avoid running hooks when no files would transfer.
- If a hook fails, the script exits with the hook's non-zero status.
- Overlapping sync triggers are coalesced; a running sync holds a lock and records a
  pending run so changes that land mid-sync are picked up once the current pass finishes.
