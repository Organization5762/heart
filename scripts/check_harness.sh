#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REQUIRED_CMDS=(uv rsync)
OPTIONAL_CMDS=(spellcheck sshpass fswatch inotifywait)
missing_required=()

if [[ ! -f "${REPO_ROOT}/pyproject.toml" ]]; then
  echo "Error: expected to find pyproject.toml in ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/sync.sh" ]]; then
  echo "Error: expected to find sync.sh in ${REPO_ROOT}" >&2
  exit 1
fi

echo "Checking harness prerequisites in ${REPO_ROOT}"

for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    missing_required+=("${cmd}")
  fi
done

if [[ ${#missing_required[@]} -gt 0 ]]; then
  echo "Missing required tools: ${missing_required[*]}" >&2
  exit 1
fi

echo "Required tools available: ${REQUIRED_CMDS[*]}"

for cmd in "${OPTIONAL_CMDS[@]}"; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    echo "Optional tool available: ${cmd}"
  else
    echo "Optional tool missing: ${cmd}"
  fi
done

if [[ -f "${REPO_ROOT}/.syncignore" ]]; then
  echo "Found .syncignore at ${REPO_ROOT}/.syncignore"
else
  echo "No .syncignore file found in ${REPO_ROOT}"
fi

