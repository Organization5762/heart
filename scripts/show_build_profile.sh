#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD_PROFILE_FILE=${BUILD_PROFILE_FILE:-"${REPO_ROOT}/scripts/build_profiles.json"}
BUILD_PROFILE=${BUILD_PROFILE:-}
BUILD_HASH_MODE=${BUILD_HASH_MODE:-}
BUILD_INPUTS_FILE=${BUILD_INPUTS_FILE:-}
BUILD_INPUTS=${BUILD_INPUTS:-}
BUILD_ARGS=${BUILD_ARGS:-}
PYTHON_BIN=${PYTHON_BIN:-}

DEFAULT_BUILD_INPUTS=(src pyproject.toml README.md uv.lock)

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "Error: python is required to inspect build profiles." >&2
    exit 1
  fi
fi

profile_inputs=()
profile_args=()
profile_hash_mode=""
profile_description=""
profile_name=""

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
print(f"PROFILE_NAME={shlex.quote(profile_name)}")
PYTHON
  )"

  profile_inputs=("${PROFILE_INPUTS[@]}")
  profile_args=("${PROFILE_ARGS[@]}")
  profile_hash_mode="${PROFILE_HASH_MODE}"
  profile_description="${PROFILE_DESCRIPTION}"
  profile_name="${PROFILE_NAME}"
fi

effective_hash_mode_source="default"
if [[ -n "${BUILD_HASH_MODE}" ]]; then
  effective_hash_mode="${BUILD_HASH_MODE}"
  effective_hash_mode_source="BUILD_HASH_MODE"
elif [[ -n "${profile_hash_mode}" ]]; then
  effective_hash_mode="${profile_hash_mode}"
  effective_hash_mode_source="profile"
else
  effective_hash_mode="content"
fi

effective_inputs_source="default"
if [[ -n "${BUILD_INPUTS_FILE}" ]]; then
  if [[ ! -f "${BUILD_INPUTS_FILE}" ]]; then
    echo "Error: BUILD_INPUTS_FILE does not exist at ${BUILD_INPUTS_FILE}" >&2
    exit 1
  fi
  mapfile -t effective_inputs < <(grep -Ev '^\s*(#|$)' "${BUILD_INPUTS_FILE}")
  effective_inputs_source="BUILD_INPUTS_FILE"
elif [[ -n "${BUILD_INPUTS}" ]]; then
  read -r -a effective_inputs <<<"${BUILD_INPUTS}"
  effective_inputs_source="BUILD_INPUTS"
elif [[ ${#profile_inputs[@]} -gt 0 ]]; then
  effective_inputs=("${profile_inputs[@]}")
  effective_inputs_source="profile"
else
  effective_inputs=("${DEFAULT_BUILD_INPUTS[@]}")
fi

effective_args_source="default"
if [[ -n "${BUILD_ARGS}" ]]; then
  read -r -a effective_args <<<"${BUILD_ARGS}"
  effective_args_source="BUILD_ARGS"
elif [[ ${#profile_args[@]} -gt 0 ]]; then
  effective_args=("${profile_args[@]}")
  effective_args_source="profile"
else
  effective_args=()
fi

echo "Build profile summary"
echo "Profile name: ${profile_name:-${BUILD_PROFILE:-none}}"
echo "Profile file: ${BUILD_PROFILE_FILE}"
if [[ -n "${profile_description}" ]]; then
  echo "Profile description: ${profile_description}"
fi
echo "Hash mode: ${effective_hash_mode} (${effective_hash_mode_source})"
if [[ ${#effective_args[@]} -gt 0 ]]; then
  echo "Build args (${effective_args_source}):"
  for arg in "${effective_args[@]}"; do
    echo "  - ${arg}"
  done
else
  echo "Build args (${effective_args_source}): none"
fi
echo "Build inputs (${effective_inputs_source}):"
if [[ ${#effective_inputs[@]} -gt 0 ]]; then
  for entry in "${effective_inputs[@]}"; do
    echo "  - ${entry}"
  done
else
  echo "  - (none)"
fi
