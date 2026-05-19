#!/usr/bin/env bash
set -u

REPO_DIR="${HEART_REPO_DIR:-/home/michael/Desktop/heart}"
RP1_PIO_DIR="${HEART_RP1_HUB75_RP1_PIO_DIR:-/home/michael/rp1-pio}"
SECONDS_PER_SCENE="${HEART_VIBE_CYCLE_SECONDS:-30}"
BRIGHTNESS="${HEART_RGB_MATRIX_BRIGHTNESS:-1.0}"
BRIGHTNESS_REFERENCE_PWM_BITS="${HEART_RGB_MATRIX_BRIGHTNESS_REFERENCE_PWM_BITS:-8}"
GAMMA="${HEART_RGB_MATRIX_GAMMA:-1.0}"
PWM_BITS="${HEART_RP1_HUB75_PWM_BITS:-11}"
LOG_PATH="${HEART_VIBE_CYCLE_LOG:-/tmp/heart-vibe-cycle.log}"

cd "${REPO_DIR}" || exit 1
export PATH="${HOME}/.cargo/bin:${HOME}/.local/bin:${PATH}"

kill_heart() {
  ps -eo pid=,comm=,args= \
    | awk '/rp1_hub75_run_candidate|rp1_sram_counter|totem run|start-heart|led-image-viewer/ && !/awk/ {print $1}' \
    | xargs -r sudo kill -9 2>/dev/null || true
}

names=(
  "sunsleeper"
  "tree"
  "heart"
  "sun"
  "sun bright"
  "overmono sheet"
  "overmono runner"
  "oppi"
)

: > "${LOG_PATH}"
kill_heart
sudo modprobe rp1-hub75 2>/dev/null || sudo modprobe rp1_hub75 2>/dev/null || true

while true; do
  for idx in "${!names[@]}"; do
    name="${names[$idx]}"
    printf "\n=== vibe[%s] %s %(%H:%M:%S)T ===\n" "${idx}" "${name}" -1 | tee -a "${LOG_PATH}"
    sudo rm -f /tmp/heart-start-heart.log /tmp/heart-sun-driver.log
    sudo timeout --signal=TERM --kill-after=3s "${SECONDS_PER_SCENE}s" env \
      PATH="${PATH}" \
      RUN_CONFIGURATION=vibe_single \
      HEART_VIBE_SCENE_INDEX="${idx}" \
      HEART_REPO_DIR="${REPO_DIR}" \
      HEART_DEVICE_LAYOUT=rectangle \
      HEART_LAYOUT_COLUMNS=4 \
      HEART_LAYOUT_ROWS=1 \
      HEART_PANEL_COLUMNS=64 \
      HEART_PANEL_ROWS=64 \
      HEART_RGB_DISPLAY_BACKEND=native \
      HEART_RGB_MATRIX_HARDWARE_MAPPING=three-port-active \
      HEART_RGB_MATRIX_BRIGHTNESS="${BRIGHTNESS}" \
      HEART_RGB_MATRIX_BRIGHTNESS_REFERENCE_PWM_BITS="${BRIGHTNESS_REFERENCE_PWM_BITS}" \
      HEART_RGB_MATRIX_GAMMA="${GAMMA}" \
      HEART_PI5_MATRIX_BACKEND=rp1-hub75 \
      HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS="${PWM_BITS}" \
      HEART_RP1_HUB75_PWM_BITS="${PWM_BITS}" \
      HEART_RP1_HUB75_EXTERNAL_SRAM_SLOT_OFFSET=0xb800 \
      HEART_RP1_HUB75_RP1_PIO_DIR="${RP1_PIO_DIR}" \
      HEART_RP1_HUB75_EXTERNAL_SCANNER=1 \
      HEART_RP1_HUB75_SCANNER_CANDIDATE=state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2 \
      HEART_RP1_HUB75_SCANNER_MEASURE_SECONDS=86400 \
      HEART_RP1_HUB75_SCANNER_BOOT_TIMEOUT_SECONDS=120 \
      HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE=0 \
      FORWARD_TO_BEATS_APP=0 \
      ./drivers/totem/start-heart.sh >> "${LOG_PATH}" 2>&1
    status=$?
    printf "=== end vibe[%s] %s status=%s %(%H:%M:%S)T ===\n" "${idx}" "${name}" "${status}" -1 | tee -a "${LOG_PATH}"
    kill_heart
    sleep 1
  done
done
