#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=drivers/totem/heart-supervisor-common.sh
. /usr/local/bin/heart-supervisor-common.sh

load_totem_env

RP1_PIO_DIR="${HEART_RP1_HUB75_RP1_PIO_DIR:-/home/michael/rp1-pio}"
RP1_SRAM_SLOT_OFFSET="${HEART_RP1_HUB75_EXTERNAL_SRAM_SLOT_OFFSET:-0xb800}"
RP1_SCANNER_CANDIDATE="${HEART_RP1_HUB75_SCANNER_CANDIDATE:-state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2}"
RP1_SCANNER_PWM_BITS="${HEART_RP1_HUB75_SCANNER_PWM_BITS:-${HEART_RP1_HUB75_PWM_BITS:-${HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS:-8}}}"
RP1_SCANNER_MEASURE_SECONDS="${HEART_RP1_HUB75_SCANNER_MEASURE_SECONDS:-86400}"
RP1_SCANNER_BOOT_TIMEOUT_SECONDS="${HEART_RP1_HUB75_SCANNER_BOOT_TIMEOUT_SECONDS:-120}"
RP1_EXPECTED_SLOT_HIGH="${HEART_RP1_HUB75_EXPECTED_SLOT_HIGH:-0x00000010}"
RP1_REQUIRE_PWM_HANDSHAKE="${HEART_RP1_HUB75_REQUIRE_PWM_HANDSHAKE:-1}"
RP1_SLOT_META_OFFSET="${HEART_RP1_HUB75_SLOT_META_OFFSET:-16}"
RP1_SCANNER_PURGE_WORDS="${HEART_RP1_HUB75_SCANNER_PURGE_WORDS:-0}"
RP1_SCANNER_PURGE_VALUE="${HEART_RP1_HUB75_SCANNER_PURGE_VALUE:-0x00000000}"
RP1_SCANNER_PURGE_MAGIC_VALUE="${HEART_RP1_HUB75_SCANNER_PURGE_MAGIC_VALUE:-}"

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

if [[ "${RP1_SCANNER_CANDIDATE}" == *nomask* ]]; then
  log "refusing unsafe scanner candidate containing nomask: ${RP1_SCANNER_CANDIDATE}"
  exit 2
fi

if (( RP1_SCANNER_PURGE_WORDS > 0 )) && [[ ! -x "${SRAM_WRITER}" ]]; then
  log "missing SRAM writer for startup purge: ${SRAM_WRITER}"
  exit 3
fi

if (( RP1_SCANNER_PURGE_WORDS > 0 )); then
  log "purging ${RP1_SCANNER_PURGE_WORDS} SRAM words at ${RP1_SRAM_SLOT_OFFSET} with ${RP1_SCANNER_PURGE_VALUE}"
  for (( word_index=0; word_index<RP1_SCANNER_PURGE_WORDS; word_index++ )); do
    "${SRAM_WRITER}" "$((RP1_SRAM_SLOT_OFFSET + word_index * 4))" "${RP1_SCANNER_PURGE_VALUE}" >/dev/null
  done

  if [[ -n "${RP1_SCANNER_PURGE_MAGIC_VALUE}" ]]; then
    "${SRAM_WRITER}" "${RP1_SRAM_SLOT_OFFSET}" "${RP1_SCANNER_PURGE_MAGIC_VALUE}" >/dev/null
    log "wrote SRAM purge magic ${RP1_SCANNER_PURGE_MAGIC_VALUE} at ${RP1_SRAM_SLOT_OFFSET}"
  fi
fi

deadline=$((SECONDS + RP1_SCANNER_BOOT_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if [[ -e /dev/rp1-hub75 && -d "${RP1_PIO_DIR}" && -x "${SRAM_READER}" && -x "${SCANNER_RUNNER}" ]]; then
    slot_low="$("${SRAM_READER}" "${RP1_SRAM_SLOT_OFFSET}" 2>/dev/null || printf '0x00000000\n')"
    slot_high="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + 4))" 2>/dev/null || printf '0x00000000\n')"
    slot_meta="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + RP1_SLOT_META_OFFSET))" 2>/dev/null || printf '0x00000000\n')"
    if [[ "${slot_low}" != "0x00000000" && "${slot_high}" == "${RP1_EXPECTED_SLOT_HIGH}" ]] && slot_meta_matches_scanner_pwm "${slot_meta}"; then
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
slot_meta="$("${SRAM_READER}" "$((RP1_SRAM_SLOT_OFFSET + RP1_SLOT_META_OFFSET))" 2>/dev/null || printf '0x00000000\n')"
if [[ "${slot_low}" == "0x00000000" || "${slot_high}" != "${RP1_EXPECTED_SLOT_HIGH}" ]]; then
  log "timed out waiting for live SRAM frame slot at ${RP1_SRAM_SLOT_OFFSET} low=${slot_low} high=${slot_high}"
  exit 3
fi
if ! slot_meta_matches_scanner_pwm "${slot_meta}"; then
  log "refusing scanner PWM mismatch: scanner pwm=${RP1_SCANNER_PWM_BITS} expected slot meta=${RP1_EXPECTED_SLOT_META} observed slot meta=${slot_meta}. Set HEART_RP1_HUB75_PWM_BITS for normal operation; use HEART_RP1_HUB75_SCANNER_PWM_BITS only for intentional mismatch experiments."
  exit 4
fi

log "launching ${RP1_SCANNER_CANDIDATE} pwm=${RP1_SCANNER_PWM_BITS} slot_meta=${slot_meta}"
cd "${RP1_PIO_DIR}"
exec env \
  RP1_HUB75_PWM_BITS="${RP1_SCANNER_PWM_BITS}" \
  RP1_HUB75_WAIT_FRAME_SLOT_AFTER_LAUNCH=1 \
  RP1_HUB75_FRAME_SLOT_OFFSET="${RP1_SRAM_SLOT_OFFSET}" \
  RP1_HUB75_FRAME_SLOT_EXPECTED_HIGH="${RP1_EXPECTED_SLOT_HIGH}" \
  RP1_HUB75_FRAME_SLOT_TIMEOUT_SECONDS="${RP1_SCANNER_BOOT_TIMEOUT_SECONDS}" \
  "${SCANNER_RUNNER}" \
  "${RP1_SCANNER_CANDIDATE}" "${RP1_SCANNER_MEASURE_SECONDS}"
