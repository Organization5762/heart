#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD_STAMP_PATH=${BUILD_STAMP_PATH:-"${REPO_ROOT}/build/.package_stamp"}
BUILD_MANIFEST_PATH=${BUILD_MANIFEST_PATH:-"${REPO_ROOT}/build/.package_manifest.json"}
BUILD_FORCE=${BUILD_FORCE:-false}
BUILD_ARGS=${BUILD_ARGS:-}
BUILD_HASH_MODE=${BUILD_HASH_MODE:-}
BUILD_INPUTS_FILE=${BUILD_INPUTS_FILE:-}
BUILD_PROFILE=${BUILD_PROFILE:-}
BUILD_PROFILE_FILE=${BUILD_PROFILE_FILE:-"${REPO_ROOT}/scripts/build_profiles.json"}
PYTHON_BIN=${PYTHON_BIN:-}

DEFAULT_BUILD_INPUTS=(src pyproject.toml README.md uv.lock)
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "Error: python is required to build the package." >&2
    exit 1
  fi
fi

profile_inputs=()
profile_args=()
profile_hash_mode=""
profile_description=""

if [[ -f "${BUILD_PROFILE_FILE}" ]] && [[ -z "${BUILD_PROFILE}" ]]; then
  BUILD_PROFILE="default"
fi

if [[ -n "${BUILD_PROFILE}" ]]; then
  if [[ ! -f "${BUILD_PROFILE_FILE}" ]]; then
    echo "Error: BUILD_PROFILE_FILE does not exist at ${BUILD_PROFILE_FILE}" >&2
    exit 1
  fi

  eval "$(
    BUILD_PROFILE_FILE="${BUILD_PROFILE_FILE}" \
    BUILD_PROFILE="${BUILD_PROFILE}" \
    "${PYTHON_BIN}" - <<'PYTHON'
import json
import os
import shlex
import sys

profile_file = os.environ["BUILD_PROFILE_FILE"]
profile_name = os.environ["BUILD_PROFILE"]

with open(profile_file, "r", encoding="utf-8") as handle:
  profiles = json.load(handle)

if profile_name not in profiles:
  available = ", ".join(sorted(profiles)) or "none"
  print(f"Error: build profile '{profile_name}' not found. Available: {available}.", file=sys.stderr)
  raise SystemExit(1)

profile = profiles[profile_name]

def _list(value, key):
  if value is None:
    return []
  if not isinstance(value, list):
    raise SystemExit(f"Build profile '{profile_name}' field '{key}' must be a list.")
  return [str(item) for item in value]

inputs = _list(profile.get("inputs", []), "inputs")
args = _list(profile.get("args", []), "args")
hash_mode = profile.get("hash_mode", "") or ""
description = profile.get("description", "") or ""

if hash_mode and hash_mode not in {"content", "metadata"}:
  raise SystemExit(f"Build profile '{profile_name}' has unsupported hash_mode '{hash_mode}'.")

def _emit_array(name, values):
  joined = " ".join(shlex.quote(item) for item in values)
  print(f"{name}=({joined})")

_emit_array("PROFILE_INPUTS", inputs)
_emit_array("PROFILE_ARGS", args)
print(f"PROFILE_HASH_MODE={shlex.quote(hash_mode)}")
print(f"PROFILE_DESCRIPTION={shlex.quote(description)}")
PYTHON
  )"

  profile_inputs=("${PROFILE_INPUTS[@]}")
  profile_args=("${PROFILE_ARGS[@]}")
  profile_hash_mode="${PROFILE_HASH_MODE}"
  profile_description="${PROFILE_DESCRIPTION}"
fi

if [[ -z "${BUILD_HASH_MODE}" ]]; then
  if [[ -n "${profile_hash_mode}" ]]; then
    BUILD_HASH_MODE="${profile_hash_mode}"
  else
    BUILD_HASH_MODE="content"
  fi
fi

if [[ -n "${BUILD_INPUTS_FILE}" ]]; then
  if [[ ! -f "${BUILD_INPUTS_FILE}" ]]; then
    echo "Error: BUILD_INPUTS_FILE does not exist at ${BUILD_INPUTS_FILE}" >&2
    exit 1
  fi
  mapfile -t build_inputs < <(grep -Ev '^\s*(#|$)' "${BUILD_INPUTS_FILE}")
elif [[ -n "${BUILD_INPUTS:-}" ]]; then
  read -r -a build_inputs <<<"${BUILD_INPUTS}"
elif [[ ${#profile_inputs[@]} -gt 0 ]]; then
  build_inputs=("${profile_inputs[@]}")
else
  build_inputs=("${DEFAULT_BUILD_INPUTS[@]}")
fi

collect_build_files() {
  if command -v git >/dev/null 2>&1; then
    git -C "${REPO_ROOT}" ls-files -z -- "${build_inputs[@]}"
    return
  fi

  for entry in "${build_inputs[@]}"; do
    if [[ -d "${REPO_ROOT}/${entry}" ]]; then
      find "${REPO_ROOT}/${entry}" -type f -print0
    elif [[ -f "${REPO_ROOT}/${entry}" ]]; then
      printf '%s\0' "${REPO_ROOT}/${entry}"
    fi
  done
}

mapfile -d '' -t build_files < <(collect_build_files)
if [[ ${#build_files[@]} -eq 0 ]]; then
  echo "Warning: no build inputs found; proceeding with build." >&2
fi

current_hash=$(printf '%s\n' "${build_files[@]}" | BUILD_HASH_MODE="${BUILD_HASH_MODE}" "${PYTHON_BIN}" - <<'PYTHON'
import hashlib
import os
import sys

mode = os.environ.get("BUILD_HASH_MODE", "content")
if mode not in {"content", "metadata"}:
  raise SystemExit(f"Unsupported BUILD_HASH_MODE: {mode}")

paths = [line.strip() for line in sys.stdin if line.strip()]
paths.sort()

hasher = hashlib.sha256()
for path in paths:
  rel_path = os.path.relpath(path)
  hasher.update(rel_path.encode())
  if mode == "metadata":
    stat = os.stat(path)
    hasher.update(str(stat.st_size).encode())
    hasher.update(str(stat.st_mtime_ns).encode())
  else:
    with open(path, "rb") as handle:
      for chunk in iter(lambda: handle.read(8192), b""):
        hasher.update(chunk)

print(hasher.hexdigest())
PYTHON
)

write_manifest() {
  local build_skipped="$1"
  local reason="$2"
  mkdir -p "$(dirname "${BUILD_MANIFEST_PATH}")"
  BUILD_INPUTS_LIST=$(printf '%s\n' "${build_inputs[@]}") \
  BUILD_HASH="${current_hash}" \
  BUILD_HASH_MODE="${BUILD_HASH_MODE}" \
  BUILD_SKIPPED="${build_skipped}" \
  BUILD_REASON="${reason}" \
  BUILD_STAMP_PATH="${BUILD_STAMP_PATH}" \
  BUILD_MANIFEST_PATH="${BUILD_MANIFEST_PATH}" \
  BUILD_ARGS="${BUILD_ARGS}" \
  BUILD_FORCE="${BUILD_FORCE}" \
  BUILD_PROFILE="${BUILD_PROFILE}" \
  BUILD_PROFILE_FILE="${BUILD_PROFILE_FILE}" \
  BUILD_PROFILE_DESCRIPTION="${profile_description}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  "${PYTHON_BIN}" - <<'PYTHON'
import json
import os
import sys
from datetime import datetime, timezone

manifest_path = os.environ["BUILD_MANIFEST_PATH"]
inputs_list = os.environ.get("BUILD_INPUTS_LIST", "")
build_inputs = [line for line in inputs_list.splitlines() if line.strip()]

def _safe_version(cmd: str) -> str:
  import subprocess

  try:
    return subprocess.check_output([cmd, "--version"], text=True).strip()
  except Exception:
    return "unknown"

manifest = {
  "timestamp": datetime.now(timezone.utc).isoformat(),
  "build_hash": os.environ.get("BUILD_HASH", ""),
  "build_hash_mode": os.environ.get("BUILD_HASH_MODE", "content"),
  "build_inputs": build_inputs,
  "build_args": os.environ.get("BUILD_ARGS", ""),
  "build_force": os.environ.get("BUILD_FORCE", "false"),
  "build_profile": os.environ.get("BUILD_PROFILE", ""),
  "build_profile_file": os.environ.get("BUILD_PROFILE_FILE", ""),
  "build_profile_description": os.environ.get("BUILD_PROFILE_DESCRIPTION", ""),
  "build_skipped": os.environ.get("BUILD_SKIPPED", "false") == "true",
  "build_reason": os.environ.get("BUILD_REASON", ""),
  "build_stamp_path": os.environ.get("BUILD_STAMP_PATH", ""),
  "python_version": _safe_version(os.environ.get("PYTHON_BIN", "python")),
  "uv_version": _safe_version("uv"),
}

with open(manifest_path, "w", encoding="utf-8") as handle:
  json.dump(manifest, handle, indent=2, sort_keys=True)
PYTHON
}

if [[ "${BUILD_FORCE}" != "true" ]] && [[ -f "${BUILD_STAMP_PATH}" ]]; then
  previous_hash=$(cat "${BUILD_STAMP_PATH}")
  if [[ "${previous_hash}" == "${current_hash}" ]]; then
    echo "Build inputs unchanged; skipping uv build."
    write_manifest "true" "inputs-unchanged"
    exit 0
  fi
fi

mkdir -p "$(dirname "${BUILD_STAMP_PATH}")"

if [[ -z "${BUILD_ARGS}" ]] && [[ ${#profile_args[@]} -gt 0 ]]; then
  BUILD_ARGS=$(printf '%s ' "${profile_args[@]}")
  BUILD_ARGS="${BUILD_ARGS%% }"
fi

build_args=()
if [[ -n "${BUILD_ARGS}" ]]; then
  read -r -a build_args <<<"${BUILD_ARGS}"
fi

uv build "${build_args[@]}"

echo "${current_hash}" > "${BUILD_STAMP_PATH}"
write_manifest "false" "build-complete"
