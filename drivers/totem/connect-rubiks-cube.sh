#!/usr/bin/env bash
set -euo pipefail

ADDRESS="${HEART_RUBIKS_CONNECTED_X_ADDRESS:-}"
ATTEMPTS="${HEART_RUBIKS_CONNECTED_X_CONNECT_ATTEMPTS:-5}"
SLEEP_SECONDS="${HEART_RUBIKS_CONNECTED_X_CONNECT_SLEEP_SECONDS:-2}"
SCAN_SECONDS="${HEART_RUBIKS_CONNECTED_X_SCAN_SECONDS:-6}"

if [[ -z "${ADDRESS}" ]]; then
  exit 0
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  exit 0
fi

( timeout "${SCAN_SECONDS}" bluetoothctl scan on >/dev/null 2>&1 ) &

for (( attempt=1; attempt<=ATTEMPTS; attempt++ )); do
  if bluetoothctl connect "${ADDRESS}" >/dev/null 2>&1; then
    exit 0
  fi
  sleep "${SLEEP_SECONDS}"
done

exit 0
