#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${HEART_REPO_DIR:-/home/michael/Desktop/heart}"
ADDRESS="${HEART_RUBIKS_CONNECTED_X_ADDRESS:-}"
ATTEMPTS="${HEART_RUBIKS_CONNECTED_X_CONNECT_ATTEMPTS:-5}"
SLEEP_SECONDS="${HEART_RUBIKS_CONNECTED_X_CONNECT_SLEEP_SECONDS:-2}"
SCAN_SECONDS="${HEART_RUBIKS_CONNECTED_X_SCAN_SECONDS:-20}"
RP1_PIO_DIR="${HEART_RP1_HUB75_RP1_PIO_DIR:-/home/michael/rp1-pio}"
RP1_SRAM_SLOT_OFFSET="${HEART_RP1_HUB75_EXTERNAL_SRAM_SLOT_OFFSET:-0xb800}"
RP1_SCANNER_CANDIDATE="${HEART_RP1_HUB75_SCANNER_CANDIDATE:-state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2}"
RP1_SCANNER_PWM_BITS="${HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS:-8}"
RP1_SCANNER_MEASURE_SECONDS="${HEART_RP1_HUB75_SCANNER_MEASURE_SECONDS:-2}"
RP1_SCANNER_BOOT_TIMEOUT_SECONDS="${HEART_RP1_HUB75_SCANNER_BOOT_TIMEOUT_SECONDS:-120}"
RP1_EXTERNAL_SCANNER="${HEART_RP1_HUB75_EXTERNAL_SCANNER:-0}"
RP1_CLEAR_SLOT_BEFORE_START="${HEART_RP1_HUB75_CLEAR_SLOT_BEFORE_START:-0}"
RP1_EXPECTED_SLOT_HIGH="${HEART_RP1_HUB75_EXPECTED_SLOT_HIGH:-0x00000010}"
RP1_REQUIRE_PWM_HANDSHAKE="${HEART_RP1_HUB75_REQUIRE_PWM_HANDSHAKE:-1}"
RP1_SLOT_META_OFFSET="${HEART_RP1_HUB75_SLOT_META_OFFSET:-16}"
HEART_START_LOG="${HEART_START_LOG:-/tmp/heart-start-heart.log}"
RUN_CONFIGURATION="${RUN_CONFIGURATION:-lib_2025}"
TOTEM_BIN="${HEART_TOTEM_BIN:-${REPO_DIR}/.venv/bin/totem}"

log() {
  printf 'start-heart: %s\n' "$*"
}

if [[ -n "${ADDRESS}" ]] && command -v bluetoothctl >/dev/null 2>&1; then
  ( timeout "${SCAN_SECONDS}" bluetoothctl scan on >/dev/null 2>&1 ) &
  for (( attempt=1; attempt<=ATTEMPTS; attempt++ )); do
    if bluetoothctl connect "${ADDRESS}" >/dev/null 2>&1; then
      break
    fi
    sleep "${SLEEP_SECONDS}"
  done
fi

cd "${REPO_DIR}"

if [[ "${RP1_EXTERNAL_SCANNER}" != "1" ]]; then
  exec make run
fi

if [[ "${RP1_SCANNER_CANDIDATE}" == *nomask* ]]; then
  log "refusing unsafe default scanner candidate containing nomask: ${RP1_SCANNER_CANDIDATE}"
  exit 2
fi

SRAM_READER="${HEART_RP1_HUB75_SRAM_READER:-${RP1_PIO_DIR}/rp1_sram_read32}"
SRAM_WRITER="${HEART_RP1_HUB75_SRAM_WRITER:-${RP1_PIO_DIR}/rp1_sram_poke32}"
SCANNER_RUNNER="${HEART_RP1_HUB75_SCANNER_RUNNER:-${RP1_PIO_DIR}/rp1_hub75_run_candidate.sh}"
RP1_EXPECTED_SLOT_META="$(printf '0x%08x' "$((0x48500000 | RP1_SCANNER_PWM_BITS))")"

normalize_hex32() {
  printf '0x%08x' "$(( $1 ))"
}

slot_meta_matches_scanner_pwm() {
  if [[ "${RP1_REQUIRE_PWM_HANDSHAKE}" != "1" ]]; then
    return 0
  fi
  [[ "$(normalize_hex32 "${1:-0x00000000}")" == "${RP1_EXPECTED_SLOT_META}" ]]
}

if [[ ! -x "${SRAM_READER}" ]]; then
  log "missing SRAM reader: ${SRAM_READER}"
  exit 2
fi

if [[ "${RP1_CLEAR_SLOT_BEFORE_START}" == "1" && ! -x "${SRAM_WRITER}" ]]; then
  log "missing SRAM writer: ${SRAM_WRITER}"
  exit 2
fi

if [[ ! -x "${SCANNER_RUNNER}" ]]; then
  log "missing scanner runner: ${SCANNER_RUNNER}"
  exit 2
fi

cleanup() {
  if [[ -n "${heart_pid:-}" ]]; then
    kill "${heart_pid}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

if [[ "${RP1_CLEAR_SLOT_BEFORE_START}" == "1" ]]; then
  "${SRAM_WRITER}" "${RP1_SRAM_SLOT_OFFSET}" 0x00000000 >/dev/null 2>&1 || true
  "${SRAM_WRITER}" "$((RP1_SRAM_SLOT_OFFSET + 4))" 0x00000000 >/dev/null 2>&1 || true
  "${SRAM_WRITER}" "$((RP1_SRAM_SLOT_OFFSET + 8))" 0x00000000 >/dev/null 2>&1 || true
  "${SRAM_WRITER}" "$((RP1_SRAM_SLOT_OFFSET + 12))" 0x00000000 >/dev/null 2>&1 || true
  "${SRAM_WRITER}" "$((RP1_SRAM_SLOT_OFFSET + RP1_SLOT_META_OFFSET))" 0x00000000 >/dev/null 2>&1 || true
  log "cleared RP1 HUB75 DMA slot at ${RP1_SRAM_SLOT_OFFSET} before starting Heart"
fi

: > "${HEART_START_LOG}"
if [[ -x "${TOTEM_BIN}" ]]; then
  heart_command=("${TOTEM_BIN}" run --configuration "${RUN_CONFIGURATION}")
else
  heart_command=(uv run totem run --configuration "${RUN_CONFIGURATION}")
fi

FORWARD_TO_BEATS_APP="${FORWARD_TO_BEATS_APP:-0}" \
BEATS_WEBSOCKET_BIND_HOST="${BEATS_WEBSOCKET_BIND_HOST:-0.0.0.0}" \
HEART_RGB_MATRIX_HARDWARE_MAPPING="${HEART_RGB_MATRIX_HARDWARE_MAPPING:-three-port-active}" \
"${heart_command[@]}" > >(tee -a "${HEART_START_LOG}") 2>&1 &
heart_pid="$!"

slot_low="0x00000000"
slot_high="0x00000000"
frame_seen=0
deadline=$((SECONDS + RP1_SCANNER_BOOT_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if ! kill -0 "${heart_pid}" >/dev/null 2>&1; then
    wait "${heart_pid}"
    exit $?
  fi

  slot_low="$("${SRAM_READER}" "${RP1_SRAM_SLOT_OFFSET}" 2>/dev/null || printf '0x00000000\n')"
  slot_high="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + 4))" 2>/dev/null || printf '0x00000000\n')"
  slot_meta="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + RP1_SLOT_META_OFFSET))" 2>/dev/null || printf '0x00000000\n')"
  if grep -q 'Sending matrix frame #[0-9].*size=(256, 64)' "${HEART_START_LOG}" 2>/dev/null; then
    frame_seen=1
  fi

  if [[ "${frame_seen}" == "1" && "${slot_low}" != "0x00000000" && "${slot_high}" == "${RP1_EXPECTED_SLOT_HIGH}" ]] && slot_meta_matches_scanner_pwm "${slot_meta}"; then
    break
  fi

  sleep 0.25
done

if [[ "${frame_seen}" != "1" || "${slot_low}" == "0x00000000" || "${slot_high}" != "${RP1_EXPECTED_SLOT_HIGH}" ]]; then
  log "timed out waiting for Heart frame and live RP1 HUB75 DMA slot at ${RP1_SRAM_SLOT_OFFSET} low=${slot_low} high=${slot_high} frame_seen=${frame_seen}"
  exit 3
fi
if ! slot_meta_matches_scanner_pwm "${slot_meta:-0x00000000}"; then
  log "refusing scanner PWM mismatch: scanner pwm=${RP1_SCANNER_PWM_BITS} expected slot meta=${RP1_EXPECTED_SLOT_META} observed slot meta=${slot_meta:-0x00000000}. Set HEART_RP1_HUB75_PWM_BITS and HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS to the same value."
  exit 4
fi

log "launching scanner ${RP1_SCANNER_CANDIDATE} pwm=${RP1_SCANNER_PWM_BITS} slot_meta=${slot_meta} after DMA slot ${slot_high}${slot_low#0x}"
(
  cd "${RP1_PIO_DIR}"
  RP1_HUB75_PWM_BITS="${RP1_SCANNER_PWM_BITS}" \
  RP1_HUB75_WAIT_FRAME_SLOT_AFTER_LAUNCH=1 \
  RP1_HUB75_FRAME_SLOT_OFFSET="${RP1_SRAM_SLOT_OFFSET}" \
  RP1_HUB75_FRAME_SLOT_EXPECTED_HIGH="${RP1_EXPECTED_SLOT_HIGH}" \
  RP1_HUB75_FRAME_SLOT_TIMEOUT_SECONDS="${RP1_SCANNER_BOOT_TIMEOUT_SECONDS}" \
  "${SCANNER_RUNNER}" \
    "${RP1_SCANNER_CANDIDATE}" "${RP1_SCANNER_MEASURE_SECONDS}"
)

wait "${heart_pid}"
