#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="/boot/firmware/config.txt"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
AUDIO_PARAM="dtparam=audio=off"
ASPM_PARAM="pcie_aspm=off"
ISOLATED_CPU_PARAM="isolcpus=3"
RGB_MATRIX_INSTALLER_URL="https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh"
RGB_MATRIX_INSTALLER_FILE="rgb-matrix.sh"

ensure_config_line() {
  local config_file="$1"
  local desired_line="$2"
  local legacy_line="$3"
  local temp_file

  temp_file="$(mktemp)"

  awk -v desired_line="$desired_line" -v legacy_line="$legacy_line" '
  BEGIN {
    found = 0
  }
  {
    if ($0 == legacy_line) {
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
  ' "$config_file" > "$temp_file"

  if ! cmp -s "$config_file" "$temp_file"; then
    sudo mv "$temp_file" "$config_file"
    echo "Updated $config_file with $desired_line"
  else
    rm "$temp_file"
    echo "$config_file already contains $desired_line"
  fi
}

ensure_cmdline_flag() {
  local cmdline_file="$1"
  local flag="$2"
  local temp_file

  if grep -q "\\b${flag}\\b" "$cmdline_file"; then
    echo "$cmdline_file already contains $flag"
    return
  fi

  temp_file="$(mktemp)"
  python3 - "$cmdline_file" "$flag" <<'PY' > "$temp_file"
from pathlib import Path
import sys

cmdline_path = Path(sys.argv[1])
flag = sys.argv[2]
current = cmdline_path.read_text(encoding="utf-8").strip()
if current:
    print(f"{current} {flag}")
else:
    print(flag)
PY
  sudo mv "$temp_file" "$cmdline_file"
  echo "Updated $cmdline_file with $flag"
}

ensure_config_line "$CONFIG_FILE" "$AUDIO_PARAM" "dtparam=audio=on"
ensure_cmdline_flag "$CMDLINE_FILE" "$ASPM_PARAM"
ensure_cmdline_flag "$CMDLINE_FILE" "$ISOLATED_CPU_PARAM"

curl "$RGB_MATRIX_INSTALLER_URL" > "$RGB_MATRIX_INSTALLER_FILE"
sudo bash "$RGB_MATRIX_INSTALLER_FILE"
