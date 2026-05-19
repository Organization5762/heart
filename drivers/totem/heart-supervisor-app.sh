#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=drivers/totem/heart-supervisor-common.sh
. /usr/local/bin/heart-supervisor-common.sh

load_totem_env

REPO_DIR="${HEART_REPO_DIR:-/home/michael/Desktop/heart}"
RUN_CONFIGURATION="${RUN_CONFIGURATION:-lib_2025}"
TOTEM_BIN="${HEART_TOTEM_BIN:-${REPO_DIR}/.venv/bin/totem}"

export DISPLAY="${DISPLAY:-:1}"
export PATH="/root/.local/bin:/home/michael/.local/bin:/home/pi/.local/bin:/root/.cargo/bin:/home/michael/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

cd "${REPO_DIR}"

if [[ -x "${TOTEM_BIN}" ]]; then
  exec "${TOTEM_BIN}" run --configuration "${RUN_CONFIGURATION}"
fi

exec uv run totem run --configuration "${RUN_CONFIGURATION}"
