#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  sudo HOTSPOT_PASSWORD='change-me' scripts/setup_pi_network.sh [options]

Configures a Raspberry Pi to:
  - prefer trusted Wi-Fi networks when available
  - fall back to a NetworkManager hotspot
  - resolve http://totem/phone on hotspot clients
  - serve the Beats web UI on port 80 through nginx
  - start the totem runtime and websocket server at boot

Options:
  --app-dir PATH          Project checkout on the Pi. Default: current directory.
  --app-user USER         User that runs the totem app. Default: SUDO_USER or current user.
  --wifi-file PATH        TSV file with trusted Wi-Fi profiles.
  --hotspot-ssid SSID     Hotspot SSID. Default: MyTotem.
  --ap-ip IP              Hotspot gateway IP. Default: 192.168.4.1.
  --configuration NAME    Totem configuration. Default: lib_2024.
  --help                  Show this help.

Environment:
  HOTSPOT_PASSWORD        WPA password for the fallback hotspot. Required.
  HOME_WIFI_PROFILE       Existing home Wi-Fi connection to prioritize. Default: preconfigured.
  HOME_WIFI_PRIORITY      Priority for HOME_WIFI_PROFILE. Default: 100.
  HOTSPOT_PRIORITY        Priority for fallback hotspot. Default: 10.
  WEB_PORT                Public nginx port. Default: 80.
  BEATS_WEB_PORT          Local Vite port. Default: 5173.
  WEBSOCKET_PORT          Runtime websocket port. Default: 8765.

Trusted Wi-Fi TSV format:
  SSID<TAB>priority<TAB>security<TAB>password

security is either "open" or "wpa-psk". Password is ignored for open networks.
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

require_root() {
  if [ "${EUID}" -ne 0 ]; then
    die "run this script with sudo"
  fi
}

APP_DIR="${APP_DIR:-$(pwd)}"
APP_USER="${APP_USER:-${SUDO_USER:-$(id -un)}}"
WIFI_FILE="${WIFI_FILE:-}"
HOTSPOT_SSID="${HOTSPOT_SSID:-MyTotem}"
HOTSPOT_PASSWORD="${HOTSPOT_PASSWORD:-}"
AP_IP="${AP_IP:-192.168.4.1}"
AP_PREFIX="${AP_PREFIX:-24}"
CONFIGURATION="${CONFIGURATION:-lib_2024}"
HOME_WIFI_PROFILE="${HOME_WIFI_PROFILE:-preconfigured}"
HOME_WIFI_PRIORITY="${HOME_WIFI_PRIORITY:-100}"
HOTSPOT_PRIORITY="${HOTSPOT_PRIORITY:-10}"
WEB_PORT="${WEB_PORT:-80}"
BEATS_WEB_PORT="${BEATS_WEB_PORT:-5173}"
WEBSOCKET_PORT="${WEBSOCKET_PORT:-8765}"
WIFI_IFACE="${WIFI_IFACE:-wlan0}"
SERVICE_NAME="${SERVICE_NAME:-heart-beats-web}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --app-user)
      APP_USER="$2"
      shift 2
      ;;
    --wifi-file)
      WIFI_FILE="$2"
      shift 2
      ;;
    --hotspot-ssid)
      HOTSPOT_SSID="$2"
      shift 2
      ;;
    --ap-ip)
      AP_IP="$2"
      shift 2
      ;;
    --configuration)
      CONFIGURATION="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

require_root

[ -n "$HOTSPOT_PASSWORD" ] || die "HOTSPOT_PASSWORD is required"
[ "${#HOTSPOT_PASSWORD}" -ge 8 ] || die "HOTSPOT_PASSWORD must be at least 8 characters"
[ -d "$APP_DIR" ] || die "APP_DIR does not exist: $APP_DIR"
[ -x "$APP_DIR/.venv/bin/totem" ] || die "missing executable: $APP_DIR/.venv/bin/totem"
have nmcli || die "nmcli is required; install NetworkManager first"
have systemctl || die "systemctl is required"

export DEBIAN_FRONTEND=noninteractive
if have apt-get; then
  apt-get update
  apt-get install -y nginx network-manager dnsmasq-base
fi

printf 'Configuring trusted Wi-Fi and hotspot profiles...\n'

if nmcli -t -f NAME connection show | grep -Fxq "$HOME_WIFI_PROFILE"; then
  nmcli connection modify "$HOME_WIFI_PROFILE" \
    connection.autoconnect yes \
    connection.autoconnect-priority "$HOME_WIFI_PRIORITY" \
    connection.autoconnect-retries 2
else
  printf 'WARN: home Wi-Fi profile not found: %s\n' "$HOME_WIFI_PROFILE" >&2
fi

if [ -n "$WIFI_FILE" ]; then
  [ -f "$WIFI_FILE" ] || die "Wi-Fi profile file does not exist: $WIFI_FILE"

  while IFS=$'\t' read -r ssid priority security password extra || [ -n "${ssid:-}" ]; do
    case "${ssid:-}" in
      ''|\#*) continue ;;
    esac

    [ -z "${extra:-}" ] || die "too many fields in Wi-Fi profile line for SSID: $ssid"
    [ -n "${priority:-}" ] || die "missing priority for SSID: $ssid"
    security="${security:-open}"

    if nmcli -t -f NAME connection show | grep -Fxq "$ssid"; then
      nmcli connection modify "$ssid" \
        802-11-wireless.ssid "$ssid" \
        connection.autoconnect yes \
        connection.autoconnect-priority "$priority" \
        connection.autoconnect-retries 2 \
        ipv4.method auto \
        ipv6.method auto
    else
      nmcli connection add type wifi ifname "$WIFI_IFACE" con-name "$ssid" ssid "$ssid" \
        connection.autoconnect yes \
        connection.autoconnect-priority "$priority" \
        connection.autoconnect-retries 2 \
        ipv4.method auto \
        ipv6.method auto
    fi

    case "$security" in
      open)
        ;;
      wpa-psk)
        [ -n "${password:-}" ] || die "missing password for WPA Wi-Fi SSID: $ssid"
        nmcli connection modify "$ssid" \
          802-11-wireless-security.key-mgmt wpa-psk \
          802-11-wireless-security.psk "$password"
        ;;
      *)
        die "unsupported security '$security' for SSID: $ssid"
        ;;
    esac
  done <"$WIFI_FILE"
fi

if nmcli -t -f NAME connection show | grep -Fxq "$HOTSPOT_SSID"; then
  nmcli connection modify "$HOTSPOT_SSID" \
    802-11-wireless.ssid "$HOTSPOT_SSID"
else
  nmcli connection add type wifi ifname "$WIFI_IFACE" con-name "$HOTSPOT_SSID" ssid "$HOTSPOT_SSID"
fi

nmcli connection modify "$HOTSPOT_SSID" \
  connection.autoconnect yes \
  connection.autoconnect-priority "$HOTSPOT_PRIORITY" \
  connection.autoconnect-retries 0 \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.psk "$HOTSPOT_PASSWORD" \
  ipv4.method shared \
  ipv4.addresses "${AP_IP}/${AP_PREFIX}" \
  ipv6.method disabled

printf 'Configuring hotspot DNS alias...\n'
install -d -m 0755 /etc/NetworkManager/dnsmasq-shared.d
cat >/etc/NetworkManager/dnsmasq-shared.d/totem.conf <<EOF
address=/totem/${AP_IP}
address=/totem.local/${AP_IP}
EOF

printf 'Configuring nginx port %s proxy...\n' "$WEB_PORT"
install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
cat >/etc/nginx/sites-available/totem <<EOF
server {
    listen ${WEB_PORT} default_server;
    listen [::]:${WEB_PORT} default_server;
    server_name totem totem.local ${AP_IP} _;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:${BEATS_WEB_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host 127.0.0.1:${BEATS_WEB_PORT};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/totem /etc/nginx/sites-enabled/totem
nginx -t

printf 'Configuring systemd service...\n'
cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Heart Beats web controller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PATH=/home/${APP_USER}/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=SDL_VIDEODRIVER=dummy
ExecStart=${APP_DIR}/.venv/bin/totem run --configuration ${CONFIGURATION} --with-beats-web --no-install-beats-deps --beats-runtime-port ${WEBSOCKET_PORT} --beats-web-host 127.0.0.1 --beats-web-port ${BEATS_WEB_PORT}
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nginx "${SERVICE_NAME}.service" >/dev/null
systemctl restart nginx
systemctl restart "${SERVICE_NAME}.service"

printf '\nConfigured Pi network stack.\n'
printf 'Home profile priority: %s=%s\n' "$HOME_WIFI_PROFILE" "$HOME_WIFI_PRIORITY"
printf 'Hotspot fallback: %s at %s/%s, priority %s\n' "$HOTSPOT_SSID" "$AP_IP" "$AP_PREFIX" "$HOTSPOT_PRIORITY"
printf 'Website: http://totem/phone on hotspot clients, or http://%s/phone\n' "$AP_IP"
printf 'WebSocket: ws://totem:%s on hotspot clients\n' "$WEBSOCKET_PORT"
printf 'SSH on hotspot: ssh %s@%s\n' "$APP_USER" "$AP_IP"

nmcli -t -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show | \
  awk -F: '$2 == "802-11-wireless" {print}'
systemctl --no-pager --full status nginx "${SERVICE_NAME}.service" | sed -n '1,80p'
