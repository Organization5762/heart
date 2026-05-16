#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUMBER=1
GEOMETRY="2304x576"
VNC_PORT=5901
REPO_DIR="$(pwd)"
CONFIGURATION="tetris"
VNC_HELPER_PATH="/usr/local/bin/setup-tetris-vnc.sh"
START_HELPER_PATH="/usr/local/bin/start-heart.sh"
START_SERVICES=1
INSTALL_PACKAGES=1

usage() {
  cat <<'EOF'
Usage: scripts/setup_tetris_vnc_autostart.sh [options]

Installs TigerVNC and configures the system totem.service to start:
  - native TigerVNC display :1
  - the Heart Tetris configuration on that display

Run this on the Pi from the Heart checkout.

Options:
  --repo DIR          Heart checkout path. Default: current directory.
  --configuration N   Heart run configuration. Default: tetris.
  --display N         X display number. Default: 1.
  --geometry WxH      VNC framebuffer size. Default: 2304x576.
  --port N            VNC TCP port. Default: 5901.
  --no-install        Do not install TigerVNC packages.
  --no-start          Create/enable services but do not start them now.
  -h, --help          Show this help.
EOF
}

log() {
  printf '[tetris-vnc-setup] %s\n' "$*"
}

fail() {
  printf '[tetris-vnc-setup] ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || fail "--repo requires a value"
      REPO_DIR="$2"
      shift 2
      ;;
    --display)
      [[ $# -ge 2 ]] || fail "--display requires a value"
      DISPLAY_NUMBER="$2"
      shift 2
      ;;
    --configuration)
      [[ $# -ge 2 ]] || fail "--configuration requires a value"
      CONFIGURATION="$2"
      shift 2
      ;;
    --geometry)
      [[ $# -ge 2 ]] || fail "--geometry requires a value"
      GEOMETRY="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || fail "--port requires a value"
      VNC_PORT="$2"
      shift 2
      ;;
    --no-install)
      INSTALL_PACKAGES=0
      shift
      ;;
    --no-start)
      START_SERVICES=0
      shift
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

run_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

install_packages() {
  if [[ "$INSTALL_PACKAGES" -eq 0 ]]; then
    return
  fi
  if command -v Xtigervnc >/dev/null 2>&1; then
    log "TigerVNC is already installed."
    return
  fi
  require_command apt-get
  log "Installing TigerVNC server."
  run_sudo apt-get update
  run_sudo apt-get install -y tigervnc-standalone-server
}

write_totem_files() {
  local display_name
  local x_socket
  local x_lock

  REPO_DIR="$(cd "$REPO_DIR" && pwd)"
  display_name=":${DISPLAY_NUMBER}"
  x_socket="/tmp/.X11-unix/X${DISPLAY_NUMBER}"
  x_lock="/tmp/.X${DISPLAY_NUMBER}-lock"

  log "Writing /etc/default/totem."
  run_sudo tee /etc/default/totem >/dev/null <<EOF
HEART_REPO_DIR=${REPO_DIR}
DISPLAY=${display_name}
X11_FORWARD=1
SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1
PERIPHERAL_CONFIGURATION=default
FORWARD_TO_BEATS_APP=0
HEART_DEVICE_LAYOUT=cube
PYTHONUNBUFFERED=1
HEART_RUN_CONFIGURATION=${CONFIGURATION}
RUN_CONFIGURATION=${CONFIGURATION}
HEART_TOTEM_EXTRA_ARGS=--no-add-low-power-mode
EOF

  log "Writing ${VNC_HELPER_PATH}."
  run_sudo tee "$VNC_HELPER_PATH" >/dev/null <<EOF
#!/usr/bin/env bash
set -euo pipefail

pkill -f "Xtigervnc ${display_name}" || true
pkill -f "Xvfb ${display_name}" || true
rm -f ${x_lock} ${x_socket}

Xtigervnc ${display_name} -geometry ${GEOMETRY} -depth 24 -rfbport ${VNC_PORT} -SecurityTypes None -localhost no -AlwaysShared=1 &

for _ in {1..30}; do
  if [[ -S ${x_socket} ]]; then
    exit 0
  fi
  sleep 1
done

exit 1
EOF
  run_sudo chmod 755 "$VNC_HELPER_PATH"

  log "Writing ${START_HELPER_PATH}."
  run_sudo tee "$START_HELPER_PATH" >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${HEART_REPO_DIR:-/home/michael/Desktop/heart}"
CONFIGURATION="${HEART_RUN_CONFIGURATION:-${RUN_CONFIGURATION:-tetris}}"
EXTRA_ARGS="${HEART_TOTEM_EXTRA_ARGS:---no-add-low-power-mode}"

/usr/local/bin/setup-tetris-vnc.sh

cd "${REPO_DIR}"

# shellcheck disable=SC2086
exec uv run totem run --configuration "${CONFIGURATION}" ${EXTRA_ARGS}
EOF
  run_sudo chmod 755 "$START_HELPER_PATH"

  log "Writing /etc/systemd/system/totem.service."
  run_sudo tee /etc/systemd/system/totem.service >/dev/null <<EOF
[Unit]
Description=Totem Service
After=multi-user.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/
Environment=HEART_REPO_DIR=${REPO_DIR}
Environment=PATH=/root/.local/bin:/home/michael/.local/bin:/home/pi/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=DISPLAY=${display_name}
Environment=MOCK_SWITCH=1
Environment=PERIPHERAL_CONFIGURATION=default
Environment=FORWARD_TO_BEATS_APP=0
Environment=HEART_DEVICE_LAYOUT=cube
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/etc/default/totem
ExecStartPre=-/usr/bin/pkill -f "uv run totem run"
ExecStartPre=-/usr/bin/pkill -f "totem run"
ExecStartPre=-/usr/bin/pkill -f "src/heart/loop.py run"
ExecStartPre=-/usr/bin/pkill -f "Xtigervnc ${display_name}"
ExecStartPre=-/usr/bin/pkill -f "Xvfb ${display_name}"
ExecStart=/bin/bash ${START_HELPER_PATH}
ExecStop=-/usr/bin/pkill -f "Xtigervnc ${display_name}"
ExecStop=-/usr/bin/pkill -f "Xvfb ${display_name}"
ExecStopPost=-/usr/bin/pkill -f "uv run totem run"
ExecStopPost=-/usr/bin/pkill -f "totem run"
ExecStopPost=-/usr/bin/pkill -f "src/heart/loop.py run"
KillMode=control-group
TimeoutStopSec=15s
SendSIGKILL=yes
Restart=always
RestartSec=3s

[Install]
WantedBy=multi-user.target
EOF
}

stop_legacy_user_services() {
  if ! command -v systemctl >/dev/null 2>&1; then
    return
  fi

  log "Stopping legacy per-user Tetris services if present."
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" \
    systemctl --user disable --now heart-tetris.service heart-tetris-vnc.service >/dev/null 2>&1 || true
  rm -f \
    "$HOME/.config/systemd/user/heart-tetris.service" \
    "$HOME/.config/systemd/user/heart-tetris-vnc.service"
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" \
    systemctl --user daemon-reload >/dev/null 2>&1 || true
}

clear_display_files() {
  local x_socket="/tmp/.X11-unix/X${DISPLAY_NUMBER}"
  local x_lock="/tmp/.X${DISPLAY_NUMBER}-lock"

  log "Clearing stale display files for :${DISPLAY_NUMBER}."
  run_sudo pkill -f "Xtigervnc :${DISPLAY_NUMBER}" || true
  run_sudo pkill -f "Xvfb :${DISPLAY_NUMBER}" || true
  run_sudo rm -f "$x_lock" "$x_socket"
}

enable_service() {
  require_command systemctl

  log "Reloading systemd and enabling totem.service."
  run_sudo systemctl daemon-reload
  run_sudo systemctl enable totem.service

  if [[ "$START_SERVICES" -eq 1 ]]; then
    log "Starting totem.service now."
    clear_display_files
    run_sudo systemctl restart totem.service
  fi
}

print_status() {
  log "Service status:"
  run_sudo systemctl --no-pager --full status totem.service || true

  log "Listening VNC sockets:"
  ss -ltnp 2>/dev/null | grep ":${VNC_PORT}" || true

  log "Current display/app processes:"
  pgrep -af "[X]tigervnc|[X]vfb|[u]v run totem run|[t]otem run" || true
}

main() {
  [[ -d "$REPO_DIR" ]] || fail "repo path does not exist: $REPO_DIR"
  install_packages
  require_command Xtigervnc
  stop_legacy_user_services
  write_totem_files
  enable_service
  print_status
  log "TigerVNC target: $(hostname -I | awk '{print $1}'):${VNC_PORT}"
}

main "$@"
