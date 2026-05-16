#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v cargo >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

if [ "$(uname -s)" = "Linux" ] && command -v apt-get >/dev/null 2>&1; then
  if [ ! -f /usr/include/piolib/piolib.h ]; then
    sudo apt-get update
    sudo apt-get install -y libpio-dev
  fi
fi

python3 --version
uv --version
cargo --version

uv sync --extra native
