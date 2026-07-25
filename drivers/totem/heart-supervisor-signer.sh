#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=drivers/totem/heart-supervisor-common.sh
. /usr/local/bin/heart-supervisor-common.sh

load_totem_env

REPO_DIR="${HEART_REPO_DIR:-/home/michael/Desktop/heart}"
SIGNER_BIN="${HEART_MANYFOLD_SIGNER_BIN:-${REPO_DIR}/.venv/bin/manyfold-machine-signer}"
SIGNER_STATE_DIRECTORY="${HEART_MANYFOLD_SIGNER_STATE_DIRECTORY:-/var/lib/heart/manyfold-signer}"
SIGNER_SOCKET="${HEART_MANYFOLD_SIGNER_SOCKET:-/run/heart-manyfold/signer.sock}"
ALLOWED_UID="${HEART_MANYFOLD_SIGNER_ALLOWED_UID:-$(id -u)}"
CREDENTIAL_LIFETIME_SECONDS="${HEART_MANYFOLD_SIGNER_CREDENTIAL_LIFETIME_SECONDS:-300}"
MAX_AUDIT_ENTRIES="${HEART_MANYFOLD_SIGNER_MAX_AUDIT_ENTRIES:-256}"
MAX_CLIENTS="${HEART_MANYFOLD_SIGNER_MAX_CLIENTS:-16}"

if [[ ! -x "${SIGNER_BIN}" ]]; then
  log "missing signer executable: ${SIGNER_BIN}"
  exit 2
fi

install -d -m 0700 "${SIGNER_STATE_DIRECTORY}" "$(dirname "${SIGNER_SOCKET}")"

exec "${SIGNER_BIN}" start \
  --state-dir "${SIGNER_STATE_DIRECTORY}" \
  --socket "${SIGNER_SOCKET}" \
  --allowed-uid "${ALLOWED_UID}" \
  --max-clients "${MAX_CLIENTS}" \
  --max-audit-entries "${MAX_AUDIT_ENTRIES}" \
  --credential-ttl-seconds "${CREDENTIAL_LIFETIME_SECONDS}"
