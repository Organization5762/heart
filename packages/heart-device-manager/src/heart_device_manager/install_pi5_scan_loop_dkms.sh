#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="heart-pi5-scan-loop"
KERNEL_MODULE_NAME="heart_pi5_scan_loop"
BATCH_TARGET_BYTES="4194304"

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../../.." && pwd)"
RUST_CARGO_TOML="${REPO_ROOT}/rust/heart_rgb_matrix_driver/Cargo.toml"
MODULE_VERSION="$(
  sed -n 's/^version = \"\\([^\"]*\\)\"$/\\1/p' "${RUST_CARGO_TOML}" | head -n 1
)"
DKMS_ROOT="/usr/src/${MODULE_NAME}-${MODULE_VERSION}"

if [[ -z "${MODULE_VERSION}" ]]; then
  echo "Failed to determine heart-rgb-matrix-driver version from ${RUST_CARGO_TOML}." >&2
  exit 1
fi

echo "Installing DKMS prerequisites..."
sudo apt-get update
sudo apt-get install -y dkms raspberrypi-kernel-headers

echo "Staging ${KERNEL_MODULE_NAME} sources in ${DKMS_ROOT}..."
sudo rm -rf "${DKMS_ROOT}"
sudo mkdir -p \
  "${DKMS_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop" \
  "${DKMS_ROOT}/rust/heart_rgb_matrix_driver/native"

sudo install -m 0644 \
  "${REPO_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/Makefile" \
  "${DKMS_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/Makefile"
sudo install -m 0644 \
  "${REPO_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/dkms.conf" \
  "${DKMS_ROOT}/dkms.conf"
sudo sed -i "s/^PACKAGE_VERSION=.*/PACKAGE_VERSION=\"${MODULE_VERSION}\"/" \
  "${DKMS_ROOT}/dkms.conf"
sudo install -m 0644 \
  "${REPO_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/heart_pi5_scan_loop.c" \
  "${DKMS_ROOT}/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/heart_pi5_scan_loop.c"
sudo install -m 0644 \
  "${REPO_ROOT}/rust/heart_rgb_matrix_driver/native/pi5_scan_loop_ioctl.h" \
  "${DKMS_ROOT}/rust/heart_rgb_matrix_driver/native/pi5_scan_loop_ioctl.h"

echo "Registering ${KERNEL_MODULE_NAME} with DKMS..."
sudo dkms remove -m "${MODULE_NAME}" -v "${MODULE_VERSION}" --all >/dev/null 2>&1 || true
sudo dkms add -m "${MODULE_NAME}" -v "${MODULE_VERSION}"
sudo dkms build -m "${MODULE_NAME}" -v "${MODULE_VERSION}"
sudo dkms install -m "${MODULE_NAME}" -v "${MODULE_VERSION}"
sudo depmod -a

echo "Persisting module load and replay defaults..."
printf '%s\n' "${KERNEL_MODULE_NAME}" | sudo tee /etc/modules-load.d/${KERNEL_MODULE_NAME}.conf >/dev/null
printf 'options %s batch_target_bytes=%s\n' "${KERNEL_MODULE_NAME}" "${BATCH_TARGET_BYTES}" | \
  sudo tee /etc/modprobe.d/${KERNEL_MODULE_NAME}.conf >/dev/null

echo "Reloading ${KERNEL_MODULE_NAME}..."
sudo modprobe -r "${KERNEL_MODULE_NAME}" 2>/dev/null || true
sudo modprobe "${KERNEL_MODULE_NAME}"

echo "${KERNEL_MODULE_NAME} DKMS install complete."
