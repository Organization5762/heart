#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=drivers/totem/heart-supervisor-common.sh
. /usr/local/bin/heart-supervisor-common.sh

load_totem_env

RP1_PIO_DIR="${HEART_RP1_HUB75_RP1_PIO_DIR:-/home/michael/rp1-pio}"
RP1_SRAM_SLOT_OFFSET="${HEART_RP1_HUB75_EXTERNAL_SRAM_SLOT_OFFSET:-0xb800}"
RP1_SCANNER_CANDIDATE="${HEART_RP1_HUB75_SCANNER_CANDIDATE:-state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2}"
RP1_SCANNER_PWM_BITS="${HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS:-8}"
RP1_SCANNER_MEASURE_SECONDS="${HEART_RP1_HUB75_SCANNER_MEASURE_SECONDS:-86400}"
RP1_SCANNER_BOOT_TIMEOUT_SECONDS="${HEART_RP1_HUB75_SCANNER_BOOT_TIMEOUT_SECONDS:-120}"
RP1_EXPECTED_SLOT_HIGH="${HEART_RP1_HUB75_EXPECTED_SLOT_HIGH:-0x00000010}"

SRAM_READER="${HEART_RP1_HUB75_SRAM_READER:-${RP1_PIO_DIR}/rp1_sram_read32}"
SCANNER_RUNNER="${HEART_RP1_HUB75_SCANNER_RUNNER:-${RP1_PIO_DIR}/rp1_hub75_run_candidate.sh}"

if [[ "${RP1_SCANNER_CANDIDATE}" == *nomask* ]]; then
  log "refusing unsafe scanner candidate containing nomask: ${RP1_SCANNER_CANDIDATE}"
  exit 2
fi

deadline=$((SECONDS + RP1_SCANNER_BOOT_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if [[ -e /dev/rp1-hub75 && -d "${RP1_PIO_DIR}" && -x "${SRAM_READER}" && -x "${SCANNER_RUNNER}" ]]; then
    slot_low="$("${SRAM_READER}" "${RP1_SRAM_SLOT_OFFSET}" 2>/dev/null || printf '0x00000000\n')"
    slot_high="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + 4))" 2>/dev/null || printf '0x00000000\n')"
    if [[ "${slot_low}" != "0x00000000" && "${slot_high}" == "${RP1_EXPECTED_SLOT_HIGH}" ]]; then
      break
    fi
  fi
  sleep 0.25
done

if [[ ! -e /dev/rp1-hub75 ]]; then
  log "missing /dev/rp1-hub75"
  exit 3
fi
if [[ ! -x "${SRAM_READER}" || ! -x "${SCANNER_RUNNER}" ]]; then
  log "missing RP1 helpers in ${RP1_PIO_DIR}"
  exit 3
fi

slot_low="$("${SRAM_READER}" "${RP1_SRAM_SLOT_OFFSET}" 2>/dev/null || printf '0x00000000\n')"
slot_high="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + 4))" 2>/dev/null || printf '0x00000000\n')"
if [[ "${slot_low}" == "0x00000000" || "${slot_high}" != "${RP1_EXPECTED_SLOT_HIGH}" ]]; then
  log "timed out waiting for live SRAM frame slot at ${RP1_SRAM_SLOT_OFFSET} low=${slot_low} high=${slot_high}"
  exit 3
fi

log "launching ${RP1_SCANNER_CANDIDATE} pwm=${RP1_SCANNER_PWM_BITS}"
cd "${RP1_PIO_DIR}"
exec env \
  RP1_HUB75_PWM_BITS="${RP1_SCANNER_PWM_BITS}" \
  RP1_HUB75_WAIT_FRAME_SLOT_AFTER_LAUNCH=1 \
  RP1_HUB75_FRAME_SLOT_OFFSET="${RP1_SRAM_SLOT_OFFSET}" \
  RP1_HUB75_FRAME_SLOT_EXPECTED_HIGH="${RP1_EXPECTED_SLOT_HIGH}" \
  RP1_HUB75_FRAME_SLOT_TIMEOUT_SECONDS="${RP1_SCANNER_BOOT_TIMEOUT_SECONDS}" \
  "${SCANNER_RUNNER}" \
  "${RP1_SCANNER_CANDIDATE}" "${RP1_SCANNER_MEASURE_SECONDS}"
