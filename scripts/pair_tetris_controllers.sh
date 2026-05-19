#!/usr/bin/env bash
set -euo pipefail

SCAN_SECONDS=15
CONNECT_RETRIES=4
RESET_PAIRINGS=0

SLOT_IDS=(0 1 2 3)
CONTROLLER_MACS=(
  "E4:17:D8:E9:76:C8"
  "E4:17:D8:43:5C:48"
  "E4:17:D8:58:22:8A"
  "E4:17:D8:91:15:35"
)
CONTROLLER_NAMES=(
  "8BitDo Lite 2"
  "8BitDo Lite 2"
  "8BitDo Lite 2"
  "8BitDo Lite 2"
)

usage() {
  cat <<'EOF'
Usage: scripts/pair_tetris_controllers.sh [--reset] [--scan-seconds N] [--connect-retries N]

Pairs, trusts, and connects the four hardcoded Tetris controllers on a Pi.

Options:
  --reset              Remove existing pairing records for these MACs first.
  --scan-seconds N     Seconds to wait for each controller to appear. Default: 15.
  --connect-retries N  Connection attempts after pairing/trust. Default: 4.
  -h, --help           Show this help.

Put each controller in pairing mode before running, or run the script again after
putting missing controllers back into pairing mode.
EOF
}

log() {
  printf '[pair-tetris] %s\n' "$*"
}

warn() {
  printf '[pair-tetris] WARNING: %s\n' "$*" >&2
}

fail() {
  printf '[pair-tetris] ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)
      RESET_PAIRINGS=1
      shift
      ;;
    --scan-seconds)
      [[ $# -ge 2 ]] || fail "--scan-seconds requires a value"
      SCAN_SECONDS="$2"
      shift 2
      ;;
    --connect-retries)
      [[ $# -ge 2 ]] || fail "--connect-retries requires a value"
      CONNECT_RETRIES="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

run_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

bt_info() {
  bluetoothctl info "$1" 2>/dev/null || true
}

bt_has_flag() {
  local mac="$1"
  local flag="$2"
  bt_info "$mac" | grep -q "$flag: yes"
}

bt_known() {
  local mac="$1"
  bluetoothctl devices 2>/dev/null | grep -qi "Device $mac "
}

load_input_modules() {
  log "Loading Bluetooth/input kernel modules."
  run_sudo modprobe uinput || warn "could not load uinput"
  run_sudo modprobe joydev || warn "could not load joydev"
  run_sudo modprobe hidp || warn "could not load hidp"
}

prepare_bluetooth() {
  log "Preparing bluetoothd."
  if command -v systemctl >/dev/null 2>&1; then
    run_sudo systemctl start bluetooth || warn "could not start bluetooth service"
  fi
  bluetoothctl power on >/dev/null
  bluetoothctl agent on >/dev/null || true
  bluetoothctl default-agent >/dev/null || true
}

scan_for_controller() {
  local mac="$1"
  local deadline=$((SECONDS + SCAN_SECONDS))

  if bt_known "$mac"; then
    return 0
  fi

  log "Scanning for $mac for up to ${SCAN_SECONDS}s."
  bluetoothctl scan on >/dev/null 2>&1 || true
  while [[ "$SECONDS" -lt "$deadline" ]]; do
    if bt_known "$mac"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

pair_controller() {
  local slot="$1"
  local mac="$2"
  local name="$3"

  log "Slot $slot: setting up $name ($mac)."

  if [[ "$RESET_PAIRINGS" -eq 1 ]]; then
    bluetoothctl remove "$mac" >/dev/null 2>&1 || true
    sleep 1
  fi

  if ! scan_for_controller "$mac"; then
    warn "Slot $slot: $mac not visible. Put this controller in pairing mode and rerun."
    return 1
  fi

  if ! bt_has_flag "$mac" "Paired"; then
    log "Slot $slot: pairing $mac."
    bluetoothctl pair "$mac" || true
    sleep 2
  fi

  if ! bt_has_flag "$mac" "Paired"; then
    warn "Slot $slot: pairing did not complete for $mac."
    return 1
  fi

  bluetoothctl trust "$mac" >/dev/null || true

  for attempt in $(seq 1 "$CONNECT_RETRIES"); do
    if bt_has_flag "$mac" "Connected"; then
      log "Slot $slot: connected."
      return 0
    fi
    log "Slot $slot: connect attempt $attempt/$CONNECT_RETRIES."
    bluetoothctl connect "$mac" || true
    sleep 3
  done

  if bt_has_flag "$mac" "Connected"; then
    log "Slot $slot: connected."
    return 0
  fi

  warn "Slot $slot: paired/trusted but not connected."
  return 1
}

print_verification() {
  log "Connected Bluetooth controllers:"
  bluetoothctl devices Connected 2>/dev/null || true

  log "Linux joystick devices:"
  if compgen -G "/sys/class/input/js*" >/dev/null; then
    for joystick_path in /sys/class/input/js*; do
      local name=""
      local uniq=""
      name="$(cat "$joystick_path/device/name" 2>/dev/null || true)"
      uniq="$(cat "$joystick_path/device/uniq" 2>/dev/null || true)"
      printf '  %s name="%s" uniq="%s"\n' "$joystick_path" "$name" "$uniq"
    done
  else
    printf '  none\n'
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY' || true
try:
    import pygame
except Exception:
    raise SystemExit(0)

pygame.init()
pygame.joystick.init()
print("[pair-tetris] pygame joysticks:")
print(f"  count={pygame.joystick.get_count()}")
for index in range(pygame.joystick.get_count()):
    joystick = pygame.joystick.Joystick(index)
    joystick.init()
    print(
        f"  {index}: name={joystick.get_name()!r} axes={joystick.get_numaxes()} "
        f"buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
    )
PY
  fi
}

main() {
  require_command bluetoothctl
  require_command grep
  require_command sed

  load_input_modules
  prepare_bluetooth

  local failures=0
  for index in "${!CONTROLLER_MACS[@]}"; do
    if ! pair_controller "${SLOT_IDS[$index]}" "${CONTROLLER_MACS[$index]}" "${CONTROLLER_NAMES[$index]}"; then
      failures=$((failures + 1))
    fi
  done

  bluetoothctl scan off >/dev/null 2>&1 || true
  print_verification

  if [[ "$failures" -gt 0 ]]; then
    fail "$failures controller(s) did not finish setup"
  fi
  log "All hardcoded Tetris controllers are paired/trusted/connected."
}

main "$@"
