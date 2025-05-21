#!/bin/bash
# Kill any existing Xvfb (don't worry if none found)
pkill Xvfb || true
# Remove lock files
rm -f /tmp/.X*-lock || true
# Start Xvfb
Xvfb :1 -screen 0 256x64x24 &
# Wait for Xvfb to start
sleep 2
# Check if Xvfb is running
if pgrep Xvfb > /dev/null; then
    exit 0  # Success
else
    exit 1  # Failed
fi