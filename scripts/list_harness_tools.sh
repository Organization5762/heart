#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TOOL_LIST_FILE="${1:-${REPO_ROOT}/scripts/harness_tools.txt}"

if [[ ! -f "${TOOL_LIST_FILE}" ]]; then
  exit 0
fi

awk '
  {
    sub(/#.*/, "", $0)
    gsub(/^[ \t]+|[ \t]+$/, "", $0)
  }
  NF { print $1 }
' "${TOOL_LIST_FILE}"
