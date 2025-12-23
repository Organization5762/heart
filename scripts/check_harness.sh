#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REQUIRED_CMDS=(uv uvx rsync)
OPTIONAL_CMDS=(spellcheck sshpass fswatch inotifywait flock)
PYTHON_CANDIDATES=(python3 python)
PYTHON_MIN_VERSION="3.11"
UV_TOOL_LIST_FILE="${REPO_ROOT}/scripts/harness_tools.txt"
missing_required=()

if [[ ! -f "${REPO_ROOT}/pyproject.toml" ]]; then
  echo "Error: expected to find pyproject.toml in ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/sync.sh" ]]; then
  echo "Error: expected to find sync.sh in ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -x "${REPO_ROOT}/sync.sh" ]]; then
  echo "Warning: sync.sh is not executable; run chmod +x ${REPO_ROOT}/sync.sh" >&2
fi

if [[ ! -f "${REPO_ROOT}/uv.lock" ]]; then
  echo "Warning: uv.lock is missing; run 'uv sync' to generate it." >&2
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

PYTHON_CMD=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    PYTHON_CMD="${candidate}"
    break
  fi
done

if [[ -z "${PYTHON_CMD}" ]]; then
  echo "Missing required tool: python (>=${PYTHON_MIN_VERSION})" >&2
  exit 1
fi

python_version=$(
  "${PYTHON_CMD}" - <<PYTHON
import sys
required = (3, 11)
version = ".".join(str(part) for part in sys.version_info[:3])
print(version)
if sys.version_info < required:
    raise SystemExit(1)
PYTHON
)
if [[ $? -ne 0 ]]; then
  echo "Error: ${PYTHON_CMD} ${python_version} is below required ${PYTHON_MIN_VERSION}" >&2
  exit 1
fi

echo "Python available: ${PYTHON_CMD} ${python_version}"
echo "Required tools available: ${REQUIRED_CMDS[*]}"
echo "uv version: $(uv --version)"
echo "uvx version: $(uvx --version)"

if [[ -f "${UV_TOOL_LIST_FILE}" ]]; then
  mapfile -t required_uv_tools < <(grep -E '^[a-zA-Z0-9_-]+' "${UV_TOOL_LIST_FILE}")
else
  required_uv_tools=()
  echo "Warning: ${UV_TOOL_LIST_FILE} not found; skipping uv tool checks." >&2
fi

if [[ ${#required_uv_tools[@]} -gt 0 ]]; then
  if uv tool list >/dev/null 2>&1; then
    mapfile -t installed_uv_tools < <(uv tool list | awk '/^[a-zA-Z0-9_-]+ v/ {print $1}')
    missing_uv_tools=()
    for tool in "${required_uv_tools[@]}"; do
      if ! printf '%s\n' "${installed_uv_tools[@]}" | grep -qx "${tool}"; then
        missing_uv_tools+=("${tool}")
      fi
    done
    if [[ ${#missing_uv_tools[@]} -gt 0 ]]; then
      echo "Warning: missing uv tools: ${missing_uv_tools[*]}. Run 'make install' to install them." >&2
    fi
  else
    echo "Warning: unable to list uv tools; run 'uv tool list' to verify installs." >&2
  fi
fi

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
