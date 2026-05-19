#!/usr/bin/env bash
set -euo pipefail

rm -f /tmp/.X1-lock
exec /usr/bin/Xvfb :1 -screen 0 128x128x24 -nolisten tcp
