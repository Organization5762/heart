#!/usr/bin/env bash
set -u

AP_IP="${AP_IP:-192.168.4.1}"
WEB_PORT="${WEB_PORT:-80}"
BEATS_WEB_PORT="${BEATS_WEB_PORT:-5173}"
WEBSOCKET_PORT="${WEBSOCKET_PORT:-8765}"
SSID="${SSID:-MyTotem}"
SERVICE_NAME="${SERVICE_NAME:-heart-beats-web}"

FAILED=0

section() {
  printf '\n== %s ==\n' "$1"
}

pass() {
  printf 'PASS: %s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
  FAILED=1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

service_active() {
  local service="$1"
  systemctl is-active --quiet "$service" 2>/dev/null
}

port_listening() {
  local port="$1"

  if have ss; then
    ss -ltn | awk '{ print $4 }' | grep -Eq "(^|:|\])(${port})$"
    return $?
  fi

  if have netstat; then
    netstat -ltn | awk '{ print $4 }' | grep -Eq "(^|:|\])(${port})$"
    return $?
  fi

  return 2
}

tcp_connect() {
  local host="$1"
  local port="$2"

  if have python3; then
    python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    with socket.create_connection((host, port), timeout=2):
        pass
except OSError:
    raise SystemExit(1)
PY
    return $?
  fi

  if have nc; then
    nc -z -w 2 "$host" "$port" >/dev/null 2>&1
    return $?
  fi

  return 2
}

section "Festival network target"
printf 'SSID: %s\n' "$SSID"
printf 'AP IP: %s\n' "$AP_IP"
printf 'Web UI: http://totem/phone or http://%s/phone\n' "$AP_IP"
printf 'WebSocket: ws://%s:%s\n' "$AP_IP" "$WEBSOCKET_PORT"
printf 'SSH: ssh <pi-user>@%s\n' "$AP_IP"

section "Interfaces"
if have ip; then
  ip -brief addr
  if ip -4 addr show | grep -q "${AP_IP}/"; then
    pass "$AP_IP is assigned to a local interface"
  else
    fail "$AP_IP is not assigned to any local interface"
  fi
else
  warn "ip command is unavailable"
fi

if have iw; then
  section "Wi-Fi state"
  iw dev
else
  warn "iw command is unavailable; cannot inspect Wi-Fi AP mode"
fi

if have nmcli; then
  section "NetworkManager profiles"
  nmcli -t -f NAME,TYPE,DEVICE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show | \
    awk -F: '$2 == "802-11-wireless" {print}'

  if nmcli -t -f NAME connection show | grep -Fxq "$SSID"; then
    pass "hotspot profile exists: $SSID"
  else
    fail "hotspot profile does not exist: $SSID"
  fi

  if nmcli -t -f NAME,DEVICE connection show --active | grep -Fxq "${SSID}:$(iw dev 2>/dev/null | awk '/Interface/ {print $2; exit}')"; then
    pass "hotspot profile is active"
  else
    warn "hotspot profile is not active; this is expected when the Pi is on trusted Wi-Fi"
  fi
else
  fail "nmcli is unavailable; NetworkManager hotspot cannot be inspected"
fi

section "System services"
if have systemctl; then
  if service_active ssh || service_active sshd; then
    pass "SSH service is active"
  else
    fail "SSH service is not active"
  fi

  if service_active NetworkManager; then
    pass "NetworkManager is active"
  else
    fail "NetworkManager is not active"
  fi

  if service_active nginx; then
    pass "nginx is active"
  else
    fail "nginx is not active"
  fi

  if service_active "$SERVICE_NAME"; then
    pass "$SERVICE_NAME is active"
  else
    fail "$SERVICE_NAME is not active"
  fi
else
  warn "systemctl is unavailable; cannot inspect services"
fi

section "Listening ports"
if port_listening "$WEB_PORT"; then
  pass "public web port $WEB_PORT is listening"
else
  fail "public web port $WEB_PORT is not listening"
fi

if port_listening "$BEATS_WEB_PORT"; then
  pass "local Beats web port $BEATS_WEB_PORT is listening"
else
  fail "local Beats web port $BEATS_WEB_PORT is not listening"
fi

if port_listening "$WEBSOCKET_PORT"; then
  pass "WebSocket port $WEBSOCKET_PORT is listening"
else
  fail "WebSocket port $WEBSOCKET_PORT is not listening"
fi

if have ss; then
  ss -ltnp 2>/dev/null | grep -E "(:${WEB_PORT}|:${BEATS_WEB_PORT}|:${WEBSOCKET_PORT}|:22)\\b" || true
fi

section "Hotspot DNS config"
if [ -r /etc/NetworkManager/dnsmasq-shared.d/totem.conf ]; then
  cat /etc/NetworkManager/dnsmasq-shared.d/totem.conf
  if grep -Eq "address=/totem/${AP_IP}$" /etc/NetworkManager/dnsmasq-shared.d/totem.conf; then
    pass "totem DNS alias points at $AP_IP"
  else
    fail "totem DNS alias is missing or points at the wrong IP"
  fi
else
  fail "/etc/NetworkManager/dnsmasq-shared.d/totem.conf is missing"
fi

section "Local connectivity"
if tcp_connect "$AP_IP" 22; then
  pass "SSH port is reachable on $AP_IP"
else
  fail "SSH port is not reachable on $AP_IP"
fi

if tcp_connect "$AP_IP" "$WEBSOCKET_PORT"; then
  pass "WebSocket TCP port is reachable on $AP_IP"
else
  fail "WebSocket TCP port is not reachable on $AP_IP"
fi

if have curl; then
  if curl -fsS --max-time 3 "http://${AP_IP}/phone" >/dev/null; then
    pass "web UI responds on http://${AP_IP}/phone"
  else
    fail "web UI does not respond on http://${AP_IP}/phone"
  fi

  if curl -fsS --max-time 3 --header "Host: totem" "http://127.0.0.1/phone" >/dev/null; then
    pass "nginx accepts Host: totem for /phone"
  else
    fail "nginx does not accept Host: totem for /phone"
  fi
else
  warn "curl is unavailable; cannot perform HTTP check"
fi

section "Result"
if [ "$FAILED" -eq 0 ]; then
  pass "festival network checks passed"
else
  fail "one or more festival network checks failed"
fi

exit "$FAILED"
