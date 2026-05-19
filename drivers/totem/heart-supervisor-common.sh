#!/usr/bin/env bash
set -euo pipefail

TOTEM_ENV_FILE="${TOTEM_ENV_FILE:-/etc/default/totem}"

load_totem_env() {
  if [[ -f "${TOTEM_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "${TOTEM_ENV_FILE}"
    set +a
  fi
}

log() {
  printf '%s: %s\n' "$(basename "$0")" "$*"
}
