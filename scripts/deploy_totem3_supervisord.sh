#!/usr/bin/env bash
set -euo pipefail

TARGET="michael@totem3.local"
REMOTE_BOOTSTRAP_DIR="${REMOTE_BOOTSTRAP_DIR:-/home/michael/heart-totem-bootstrap}"
REMOTE_HEART_DIR="${REMOTE_HEART_DIR:-/home/michael/Desktop/heart}"
REMOTE_RP1_DIR="${REMOTE_RP1_DIR:-/home/michael/rp1-pio}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_MODE="${BOOTSTRAP_MODE:---offline}"
BOOTSTRAP_ONLY=0

log() {
  printf 'deploy-totem3-supervisord: %s\n' "$*"
}

usage() {
  cat <<'EOF'
usage: deploy_totem3_supervisord.sh [--offline | --online] [--bootstrap-only] [--target michael@totem3.local]
       deploy_totem3_supervisord.sh [--offline | --online] [--bootstrap-only] [michael@totem3.local]

Default: --offline, michael@totem3.local

Offline mode stages only bootstrap/RP1 support files, installs from
already-available apt/package caches and local toolchains, and runs uv in
offline mode. It does not sync the Heart worktree. Use --online once to allow
apt/uv/Rust bootstrap before relying on the offline path across reboots.

Use --bootstrap-only after files are already staged in the persistent bootstrap
directory on the target. It skips staging and RP1 bundle deployment, and only
reruns the target-side bootstrap.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --offline)
      BOOTSTRAP_MODE="--offline"
      ;;
    --online)
      BOOTSTRAP_MODE="--online"
      ;;
    --bootstrap-only)
      BOOTSTRAP_ONLY=1
      ;;
    --target)
      shift
      if [[ "$#" -eq 0 ]]; then
        usage >&2
        exit 2
      fi
      TARGET="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      usage >&2
      exit 2
      ;;
    *)
      TARGET="$1"
      ;;
  esac
  shift
done

log "target=${TARGET}"
log "bootstrap_mode=${BOOTSTRAP_MODE}"

if [[ "${BOOTSTRAP_ONLY}" != "1" ]]; then
  ssh "${TARGET}" "rm -rf '${REMOTE_BOOTSTRAP_DIR}' && mkdir -p '${REMOTE_BOOTSTRAP_DIR}/drivers/totem' '${REMOTE_BOOTSTRAP_DIR}/scripts' '${REMOTE_BOOTSTRAP_DIR}/rp1/linux'"

  log "staging bootstrap files to ${REMOTE_BOOTSTRAP_DIR}"
  rsync -az "${ROOT_DIR}/drivers/totem/" "${TARGET}:${REMOTE_BOOTSTRAP_DIR}/drivers/totem/"
  rsync -az "${ROOT_DIR}/scripts/rp1_hub75_linux_bundle.py" "${TARGET}:${REMOTE_BOOTSTRAP_DIR}/scripts/"
  rsync -az "${ROOT_DIR}/rp1/linux/" "${TARGET}:${REMOTE_BOOTSTRAP_DIR}/rp1/linux/"
else
  log "bootstrap_only=1; skipping repo sync and RP1 bundle deploy"
  BOOTSTRAP_ROOT="${REMOTE_BOOTSTRAP_DIR}"
  ssh "${TARGET}" "test -f '${BOOTSTRAP_ROOT}/drivers/totem/bootstrap-supervisord.sh'"
fi

ssh "${TARGET}" "cd '${BOOTSTRAP_ROOT:-${REMOTE_BOOTSTRAP_DIR}}' && sudo bash drivers/totem/bootstrap-supervisord.sh '${BOOTSTRAP_MODE}'"
if [[ "${BOOTSTRAP_ONLY}" != "1" ]]; then
  uv run python "${ROOT_DIR}/scripts/rp1_hub75_linux_bundle.py" deploy-target \
    --host "${TARGET}" \
    --remote-dir "${REMOTE_RP1_DIR}" \
    --local-bootstrap-dir "${REMOTE_BOOTSTRAP_DIR}"
fi

ssh "${TARGET}" "sudo supervisorctl reread && sudo supervisorctl update && sudo supervisorctl status heart-app heart-rp1-scanner || true"
