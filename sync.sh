#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REMOTE_HOST="michael@totem.local"
DEFAULT_REMOTE_DIR="~/Desktop/"
DEFAULT_REMOTE_PASS="totemlib2024"

SCRIPT_NAME=$(basename "$0")

print_usage() {
  cat <<USAGE
Usage: $SCRIPT_NAME [options]

Synchronise a local directory with a remote destination using rsync.

Options:
  -s, --source DIR         Local directory to synchronise (default: current directory)
  -d, --destination DEST   Override rsync destination (default: ${DEFAULT_REMOTE_HOST}:${DEFAULT_REMOTE_DIR})
  -i, --ignore PATTERN     Additional rsync exclude pattern (may be supplied multiple times)
      --ignore-from FILE   Read rsync exclude patterns from FILE
      --once               Perform a single sync and exit (no file watching)
      --watcher MODE       Watch implementation to use: auto, fswatch, inotifywait, poll (default: auto)
      --poll-interval SEC  Interval in seconds for polling when watcher=poll (default: 5)
      --dry-run            Show what would be transferred without making changes
      --skip-spellcheck    Skip running spellcheck before synchronising
  -h, --help               Show this help message and exit

Environment variables:
  SYNC_SOURCE_DIR, SYNC_DESTINATION, SYNC_IGNORE_FILE,
  SYNC_POLL_INTERVAL, SYNC_WATCHER, SYNC_DRY_RUN,
  REMOTE_HOST, REMOTE_DIR, REMOTE_PASS

A .syncignore file inside the source directory will be used automatically
if present and no --ignore-from option is supplied.
USAGE
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

SOURCE_DIR=${SYNC_SOURCE_DIR:-$(pwd)}
REMOTE_HOST=${REMOTE_HOST:-$DEFAULT_REMOTE_HOST}
REMOTE_DIR=${REMOTE_DIR:-$DEFAULT_REMOTE_DIR}
REMOTE_PASS=${REMOTE_PASS:-$DEFAULT_REMOTE_PASS}
DESTINATION=${SYNC_DESTINATION:-${REMOTE_HOST}:${REMOTE_DIR}}
IGNORE_FILE=${SYNC_IGNORE_FILE:-}
POLL_INTERVAL=${SYNC_POLL_INTERVAL:-5}
WATCH_MODE=${SYNC_WATCHER:-auto}
DRY_RUN=${SYNC_DRY_RUN:-false}
SPELLCHECK_ENABLED=true
RUN_ONCE=false

declare -a IGNORE_PATTERNS

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--source)
      SOURCE_DIR="$2"
      shift 2
      ;;
    -d|--destination)
      DESTINATION="$2"
      shift 2
      ;;
    -i|--ignore)
      IGNORE_PATTERNS+=("$2")
      shift 2
      ;;
    --ignore-from)
      IGNORE_FILE="$2"
      shift 2
      ;;
    --once)
      RUN_ONCE=true
      shift
      ;;
    --watcher)
      WATCH_MODE="$2"
      shift 2
      ;;
    --poll-interval)
      POLL_INTERVAL="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --skip-spellcheck)
      SPELLCHECK_ENABLED=false
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Error: source directory '$SOURCE_DIR' does not exist" >&2
  exit 1
fi

SOURCE_DIR=$(cd "$SOURCE_DIR" && pwd)

if [[ -z "$IGNORE_FILE" && -f "$SOURCE_DIR/.syncignore" ]]; then
  IGNORE_FILE="$SOURCE_DIR/.syncignore"
fi

if ! command_exists rsync; then
  echo "Error: rsync is required but was not found in PATH" >&2
  exit 1
fi

case "$WATCH_MODE" in
  auto)
    if command_exists fswatch; then
      WATCH_MODE=fswatch
    elif command_exists inotifywait; then
      WATCH_MODE=inotifywait
    else
      WATCH_MODE=poll
    fi
    ;;
  fswatch|inotifywait|poll)
    ;;
  *)
    echo "Unknown watcher '$WATCH_MODE'. Supported: auto, fswatch, inotifywait, poll" >&2
    exit 1
    ;;
  esac

if [[ "$WATCH_MODE" == "inotifywait" ]] && ! command_exists inotifywait; then
  echo "Error: inotifywait is not available" >&2
  exit 1
fi

if [[ "$WATCH_MODE" == "fswatch" ]] && ! command_exists fswatch; then
  echo "Error: fswatch is not available" >&2
  exit 1
fi

if ! [[ "$POLL_INTERVAL" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "Error: poll interval must be numeric" >&2
  exit 1
fi

RSYNC_FLAGS=(-az --delete)
declare -a RSYNC_PREFIX=()
if [[ -n "$REMOTE_PASS" ]]; then
  if command_exists sshpass; then
    RSYNC_PREFIX=(sshpass -p "$REMOTE_PASS")
  else
    echo "Warning: REMOTE_PASS is set but sshpass is not available; continuing without password helper." >&2
  fi
fi
if [[ "$DRY_RUN" == true ]]; then
  RSYNC_FLAGS+=(--dry-run)
fi

for pattern in "${IGNORE_PATTERNS[@]:-}"; do
  RSYNC_FLAGS+=("--exclude=$pattern")
done

if [[ -n "$IGNORE_FILE" ]]; then
  RSYNC_FLAGS+=("--exclude-from=$IGNORE_FILE")
fi

sync_changes() {
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[$timestamp] Syncing $SOURCE_DIR -> $DESTINATION"
  run_spellcheck
  run_rsync
  echo "[$timestamp] Sync complete"
}

run_spellcheck() {
  if [[ "$SPELLCHECK_ENABLED" != true ]]; then
    return
  fi

  if ! command_exists spellcheck; then
    echo "spellcheck command not found; skipping spellcheck" >&2
    SPELLCHECK_ENABLED=false
    return
  fi

  local spellcheck_args=("--source" "$SOURCE_DIR")

  if [[ -n "$DESTINATION" ]]; then
    spellcheck_args+=("--destination" "$DESTINATION")
  fi

  echo "Running spellcheck on $SOURCE_DIR"
  if ! spellcheck "${spellcheck_args[@]}"; then
    echo "spellcheck reported issues" >&2
  fi
}

run_rsync() {
  local rsync_cmd=(rsync "${RSYNC_FLAGS[@]}" "$SOURCE_DIR"/ "$DESTINATION")

  if [[ ${#RSYNC_PREFIX[@]} -gt 0 ]]; then
    "${RSYNC_PREFIX[@]}" "${rsync_cmd[@]}"
  else
    "${rsync_cmd[@]}"
  fi
}

perform_watch() {
  case "$WATCH_MODE" in
    fswatch)
      fswatch -o -r "$SOURCE_DIR" | while read -r _; do
        sync_changes
      done
      ;;
    inotifywait)
      inotifywait -m -r -e modify,create,delete,move "$SOURCE_DIR" | while read -r _; do
        sync_changes
      done
      ;;
    poll)
      while true; do
        sleep "$POLL_INTERVAL"
        sync_changes
      done
      ;;
  esac
}

echo "Source directory: $SOURCE_DIR"
echo "Destination: $DESTINATION"
echo "Watcher: $WATCH_MODE"
if [[ -n "$IGNORE_FILE" ]]; then
  echo "Using ignore file: $IGNORE_FILE"
fi

sync_changes

if [[ "$RUN_ONCE" == true ]]; then
  exit 0
fi

echo "Watching for changes..."
perform_watch
