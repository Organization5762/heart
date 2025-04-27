#!/usr/bin/env bash
set -euo pipefail

echo '► Installing udev rule for ANT+ USB sticks…'

sudo tee /etc/udev/rules.d/42-ant-usb-sticks.rules >/dev/null <<'UDEV'
# All Dynastream/Garmin ANT+ sticks (vendor 0fcf, any product)
SUBSYSTEM=="usb", ATTR{idVendor}=="0fcf", MODE="0660", GROUP="plugdev"
# CooSpo CYCPLUS CYANT‑U01
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="e024", MODE="0660", GROUP="plugdev"
UDEV

# Reload rules and apply them to already‑plugged devices
sudo udevadm control --reload-rules
# Re‑evaluate only the matching USB devices so other hardware isn’t touched
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=0fcf
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=1a86

# Ensure the current user can access GROUP=plugdev devices
if ! id -nG "$USER" | grep -qw plugdev; then
  echo '► Adding you to the plugdev group…'
  sudo usermod -aG plugdev "$USER"
  echo '   → Log out and back in (or run “newgrp plugdev”) so the new group is active.'
fi

echo '✔  Done.  /dev/bus/usb/* ANT+ nodes should now appear as crw-rw---- root plugdev'
