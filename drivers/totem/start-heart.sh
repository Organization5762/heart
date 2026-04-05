#!/usr/bin/env bash
set -euo pipefail

ADDRESS="${HEART_RUBIKS_CONNECTED_X_ADDRESS:-}"
ATTEMPTS="${HEART_RUBIKS_CONNECTED_X_CONNECT_ATTEMPTS:-5}"
SLEEP_SECONDS="${HEART_RUBIKS_CONNECTED_X_CONNECT_SLEEP_SECONDS:-2}"
SCAN_SECONDS="${HEART_RUBIKS_CONNECTED_X_SCAN_SECONDS:-20}"

if [[ -n "${ADDRESS}" ]] && command -v bluetoothctl >/dev/null 2>&1; then
  ( timeout "${SCAN_SECONDS}" bluetoothctl scan on >/dev/null 2>&1 ) &
  for (( attempt=1; attempt<=ATTEMPTS; attempt++ )); do
    if bluetoothctl connect "${ADDRESS}" >/dev/null 2>&1; then
      break
    fi
    sleep "${SLEEP_SECONDS}"
  done
fi

exec /usr/bin/python3 /home/michael/Desktop/heart/src/heart/loop.py run --no-add-low-power-mode
