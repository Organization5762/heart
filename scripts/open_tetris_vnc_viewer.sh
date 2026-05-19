#!/usr/bin/env bash
set -euo pipefail

HOST="totem3.local"
PORT=5901
START_REMOTE=0
SSH_USER="michael"
SSH_KEY=""
VIEWER_PATH="${VNC_VIEWER:-}"

usage() {
  cat <<'EOF'
Usage: scripts/open_tetris_vnc_viewer.sh [options] [host]

Opens the TigerVNC viewer for a Tetris VNC display.

Options:
  --host HOST          Target host. Default: totem3.local.
  --port N            VNC port. Default: 5901.
  --start-remote      Restart totem.service over SSH before opening.
  --user USER         SSH user for --start-remote. Default: michael.
  --key PATH          SSH identity file for --start-remote.
  --viewer PATH       TigerVNC Viewer executable path.
  -h, --help          Show this help.

If --viewer is omitted, the script tries the standard macOS TigerVNC app, then
falls back to opening vnc://HOST:PORT.
EOF
}

log() {
  printf '[open-tetris-vnc] %s\n' "$*"
}

fail() {
  printf '[open-tetris-vnc] ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || fail "--host requires a value"
      HOST="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || fail "--port requires a value"
      PORT="$2"
      shift 2
      ;;
    --start-remote)
      START_REMOTE=1
      shift
      ;;
    --user)
      [[ $# -ge 2 ]] || fail "--user requires a value"
      SSH_USER="$2"
      shift 2
      ;;
    --key)
      [[ $# -ge 2 ]] || fail "--key requires a value"
      SSH_KEY="$2"
      shift 2
      ;;
    --viewer)
      [[ $# -ge 2 ]] || fail "--viewer requires a value"
      VIEWER_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      fail "unknown argument: $1"
      ;;
    *)
      HOST="$1"
      shift
      ;;
  esac
done

ssh_start_remote() {
  local ssh_args=()
  if [[ -n "$SSH_KEY" ]]; then
    ssh_args+=("-i" "$SSH_KEY" "-o" "IdentitiesOnly=yes")
  fi
  log "Restarting totem.service on ${SSH_USER}@${HOST}."
  ssh "${ssh_args[@]}" "${SSH_USER}@${HOST}" \
    'sudo systemctl restart totem.service'
}

wait_for_vnc() {
  if ! command -v nc >/dev/null 2>&1; then
    return
  fi
  log "Waiting for ${HOST}:${PORT}."
  for _ in {1..30}; do
    if nc -z "$HOST" "$PORT" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done
  fail "timed out waiting for ${HOST}:${PORT}"
}

open_viewer() {
  local mac_app="/Applications/TigerVNC viewer 1.15.0.app"
  local mac_viewer="/Applications/TigerVNC viewer 1.15.0.app/Contents/MacOS/TigerVNC viewer"

  if [[ -n "$VIEWER_PATH" ]]; then
    [[ -x "$VIEWER_PATH" ]] || fail "viewer is not executable: $VIEWER_PATH"
    log "Opening $HOST:$PORT with $VIEWER_PATH."
    "$VIEWER_PATH" "${HOST}:${PORT}" >/tmp/tetris-vnc-viewer.log 2>&1 &
    return
  fi

  if [[ -d "$mac_app" ]] && command -v open >/dev/null 2>&1; then
    log "Opening $HOST:$PORT with TigerVNC Viewer."
    open -na "$mac_app" --args "${HOST}:${PORT}"
    return
  fi

  if [[ -x "$mac_viewer" ]]; then
    log "Opening $HOST:$PORT with TigerVNC Viewer."
    "$mac_viewer" "${HOST}:${PORT}" >/tmp/tetris-vnc-viewer.log 2>&1 &
    return
  fi

  if command -v open >/dev/null 2>&1; then
    log "Opening vnc://$HOST:$PORT."
    open "vnc://${HOST}:${PORT}"
    return
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    log "Opening vnc://$HOST:$PORT."
    xdg-open "vnc://${HOST}:${PORT}" >/tmp/tetris-vnc-viewer.log 2>&1 &
    return
  fi

  fail "could not find a VNC viewer launcher"
}

if [[ "$START_REMOTE" -eq 1 ]]; then
  ssh_start_remote
  wait_for_vnc
fi

open_viewer
