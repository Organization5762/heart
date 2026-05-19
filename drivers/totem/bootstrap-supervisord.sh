#!/usr/bin/env bash
set -euo pipefail

TOTEM_DRIVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_EXAMPLE="${TOTEM_ENV_EXAMPLE:-${TOTEM_DRIVER_DIR}/totem3.env.example}"
TOTEM_ENV_FILE="${TOTEM_ENV_FILE:-/etc/default/totem}"
CONFIG_FILE="${CONFIG_FILE:-/boot/firmware/config.txt}"
CMDLINE_FILE="${CMDLINE_FILE:-/boot/firmware/cmdline.txt}"
REBOOT_REQUIRED=0
ONLINE_BOOTSTRAP=0

APT_PACKAGES=(
  build-essential
  ca-certificates
  clang
  curl
  git
  lld
  llvm
  make
  pkg-config
  python3
  python3-venv
  supervisor
  xvfb
)

log() {
  printf 'bootstrap-supervisord: %s\n' "$*"
}

usage() {
  cat <<'EOF'
usage: bootstrap-supervisord.sh [--offline | --online]

Default: --offline

Offline mode only uses already-installed tools, apt package cache/local package
sources, and files staged by the deploy wrapper. Online mode may run apt-get
update and fetch uv/Rust installers when missing.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --offline)
      ONLINE_BOOTSTRAP=0
      ;;
    --online)
      ONLINE_BOOTSTRAP=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

install_apt_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    log "apt-get not found; skipping package install"
    return
  fi

  local kernel_headers="linux-headers-$(uname -r)"
  local apt_flags=(-y)
  local packages=("${APT_PACKAGES[@]}")
  if [[ "${ONLINE_BOOTSTRAP}" == "1" ]]; then
    run_root apt-get update
  else
    apt_flags+=(--no-download)
  fi

  if apt-cache show "${kernel_headers}" >/dev/null 2>&1; then
    packages+=("${kernel_headers}")
  elif apt-cache show raspberrypi-kernel-headers >/dev/null 2>&1; then
    packages+=(raspberrypi-kernel-headers)
  else
    log "kernel headers package unavailable in apt metadata; module build may fail"
  fi

  if ! run_root env DEBIAN_FRONTEND=noninteractive apt-get install "${apt_flags[@]}" "${packages[@]}"; then
    if [[ "${ONLINE_BOOTSTRAP}" != "1" ]]; then
      log "offline apt install failed; run once with --online to populate packages, then rerun offline"
      exit 2
    fi
    exit 2
  fi
}

install_uv_and_rust() {
  export PATH="${HOME}/.cargo/bin:${HOME}/.local/bin:${PATH}"

  if ! command -v uv >/dev/null 2>&1; then
    if [[ "${ONLINE_BOOTSTRAP}" != "1" ]]; then
      log "uv is missing; install/preload uv or rerun one time with --online"
      exit 2
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi

  if ! command -v rustup >/dev/null 2>&1; then
    if [[ "${ONLINE_BOOTSTRAP}" != "1" ]]; then
      log "rustup is missing; install/preload Rust or rerun one time with --online"
      exit 2
    fi
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
    export PATH="${HOME}/.cargo/bin:${PATH}"
  fi

  if [[ "${ONLINE_BOOTSTRAP}" == "1" ]]; then
    rustup toolchain install stable
    rustup default stable
  fi

  if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
    log "cargo/rustc missing; install a Rust toolchain before offline bootstrap"
    exit 2
  fi
}

sync_heart_environment() {
  local repo_dir
  local uv_flags=()

  repo_dir="$(read_env_value HEART_REPO_DIR /home/michael/Desktop/heart)"
  if [[ ! -d "${repo_dir}" ]]; then
    log "Heart repo directory is missing: ${repo_dir}"
    exit 2
  fi

  if [[ "${ONLINE_BOOTSTRAP}" != "1" ]]; then
    uv_flags+=(--offline)
  fi

  (
    cd "${repo_dir}"
    uv sync --all-extras --group dev "${uv_flags[@]}"
  )
}

read_env_value() {
  local key="$1"
  local default_value="$2"
  local value=""

  if [[ -f "${TOTEM_ENV_FILE}" ]]; then
    value="$(awk -F= -v key="${key}" '$1 == key { print substr($0, length(key) + 2); exit }' "${TOTEM_ENV_FILE}")"
  fi

  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
  else
    printf '%s\n' "${default_value}"
  fi
}

ensure_config_line() {
  local config_file="$1"
  local desired_line="$2"
  local legacy_line="${3:-}"
  local temp_file

  if [[ ! -f "${config_file}" ]]; then
    log "missing ${config_file}; skipping ${desired_line}"
    return
  fi

  temp_file="$(mktemp)"
  awk -v desired_line="${desired_line}" -v legacy_line="${legacy_line}" '
    BEGIN { found = 0 }
    {
      if (legacy_line != "" && $0 == legacy_line) {
        if (!found) {
          print desired_line
          found = 1
        }
        next
      }
      if ($0 == desired_line) {
        found = 1
      }
      print $0
    }
    END {
      if (!found) {
        print desired_line
      }
    }
  ' "${config_file}" > "${temp_file}"

  if ! cmp -s "${config_file}" "${temp_file}"; then
    run_root install -m 0644 "${temp_file}" "${config_file}"
    REBOOT_REQUIRED=1
    log "updated ${config_file} with ${desired_line}"
  else
    log "${config_file} already contains ${desired_line}"
  fi
  rm -f "${temp_file}"
}

ensure_cmdline_flag() {
  local cmdline_file="$1"
  local flag="$2"
  local temp_file

  if [[ ! -f "${cmdline_file}" ]]; then
    log "missing ${cmdline_file}; skipping ${flag}"
    return
  fi

  if grep -q "\\b${flag}\\b" "${cmdline_file}"; then
    log "${cmdline_file} already contains ${flag}"
    return
  fi

  temp_file="$(mktemp)"
  python3 - "${cmdline_file}" "${flag}" > "${temp_file}" <<'PY'
from pathlib import Path
import sys

cmdline_path = Path(sys.argv[1])
flag = sys.argv[2]
current = cmdline_path.read_text(encoding="utf-8").strip()
print(f"{current} {flag}" if current else flag)
PY
  run_root install -m 0644 "${temp_file}" "${cmdline_file}"
  rm -f "${temp_file}"
  REBOOT_REQUIRED=1
  log "updated ${cmdline_file} with ${flag}"
}

merge_env_file() {
  local example_file="$1"
  local target_file="$2"
  local temp_file

  if [[ ! -f "${example_file}" ]]; then
    log "missing env example: ${example_file}"
    exit 2
  fi

  temp_file="$(mktemp)"
  if [[ -f "${target_file}" ]]; then
    cp "${target_file}" "${temp_file}"
  fi

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
    key="${line%%=*}"
    if ! grep -q "^${key}=" "${temp_file}" 2>/dev/null; then
      printf '%s\n' "${line}" >> "${temp_file}"
    fi
  done < "${example_file}"

  if [[ ! -f "${target_file}" ]] || ! cmp -s "${target_file}" "${temp_file}"; then
    run_root install -m 0644 "${temp_file}" "${target_file}"
    log "updated ${target_file}"
  else
    log "${target_file} already up to date"
  fi
  rm -f "${temp_file}"
}

install_supervisor_files() {
  run_root install -d -m 0755 /usr/local/bin /etc/supervisor/conf.d /etc/systemd/system/supervisor.service.d /etc/udev/rules.d /var/log/heart
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/setup-performance.sh" /usr/local/bin/setup-totem-performance.sh
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/setup-xvfb.sh" /usr/local/bin/setup-xvfb.sh
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/heart-supervisor-common.sh" /usr/local/bin/heart-supervisor-common.sh
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/heart-supervisor-xvfb.sh" /usr/local/bin/heart-supervisor-xvfb.sh
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/heart-supervisor-app.sh" /usr/local/bin/heart-supervisor-app.sh
  run_root install -m 0755 "${TOTEM_DRIVER_DIR}/heart-supervisor-rp1-scanner.sh" /usr/local/bin/heart-supervisor-rp1-scanner.sh
  printf 'KERNEL=="rp1-hub75", GROUP="gpio", MODE="0660"\n' | run_root tee /etc/udev/rules.d/99-rp1-hub75.rules >/dev/null
  printf 'rp1_hub75\n' | run_root tee /etc/modules-load.d/rp1-hub75.conf >/dev/null
  run_root udevadm control --reload-rules || true
  run_root udevadm trigger --name-match=rp1-hub75 || true
  run_root install -m 0644 "${TOTEM_DRIVER_DIR}/totem-performance.service" /etc/systemd/system/totem-performance.service
  run_root install -m 0644 "${TOTEM_DRIVER_DIR}/heart-totem.supervisor.conf" /etc/supervisor/conf.d/heart-totem.conf
  run_root install -m 0644 "${TOTEM_DRIVER_DIR}/supervisor-systemd-override.conf" /etc/systemd/system/supervisor.service.d/heart-totem.conf
  run_root systemctl daemon-reload
  run_root systemctl enable --now totem-performance.service
  run_root systemctl enable supervisor.service
  run_root systemctl disable --now totem.service >/dev/null 2>&1 || true
  run_root systemctl start supervisor.service
  run_root systemctl is-active --quiet supervisor.service
  run_root supervisorctl reread || true
  run_root supervisorctl update || true
}

ensure_config_line "${CONFIG_FILE}" "dtparam=audio=off" "dtparam=audio=on"
ensure_cmdline_flag "${CMDLINE_FILE}" "pcie_aspm=off"
ensure_cmdline_flag "${CMDLINE_FILE}" "isolcpus=3"
install_apt_packages
install_uv_and_rust
merge_env_file "${ENV_EXAMPLE}" "${TOTEM_ENV_FILE}"
sync_heart_environment
install_supervisor_files

log "REBOOT_REQUIRED=${REBOOT_REQUIRED}"
