#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
REQUIRED_CMDS=(uv rsync)
OPTIONAL_CMDS=(spellcheck sshpass fswatch inotifywait make)
missing_required=()

source "${SCRIPT_DIR}/harness_utils.sh"

harness_require_file "${REPO_ROOT}/pyproject.toml"
harness_require_file "${REPO_ROOT}/sync.sh"
harness_require_file "${REPO_ROOT}/Makefile"

echo "Checking harness prerequisites in ${REPO_ROOT}"

harness_collect_missing_commands missing_required "${REQUIRED_CMDS[@]}"

if [[ ${#missing_required[@]} -gt 0 ]]; then
  echo "Missing required tools: ${missing_required[*]}" >&2
  exit 1
fi

echo "Required tools available: ${REQUIRED_CMDS[*]}"
harness_report_tool_versions "${REQUIRED_CMDS[@]}"
harness_report_optional_commands "${OPTIONAL_CMDS[@]}"

if [[ -f "${REPO_ROOT}/.syncignore" ]]; then
  echo "Found .syncignore at ${REPO_ROOT}/.syncignore"
else
  echo "No .syncignore file found in ${REPO_ROOT}"
fi
