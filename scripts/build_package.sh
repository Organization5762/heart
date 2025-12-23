#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD_STAMP_PATH=${BUILD_STAMP_PATH:-"${REPO_ROOT}/build/.package_stamp"}
BUILD_FORCE=${BUILD_FORCE:-false}
BUILD_ARGS=${BUILD_ARGS:-}

DEFAULT_BUILD_INPUTS=(src pyproject.toml README.md uv.lock)
if [[ -n "${BUILD_INPUTS:-}" ]]; then
  read -r -a build_inputs <<<"${BUILD_INPUTS}"
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

current_hash=$(printf '%s\n' "${build_files[@]}" | python - <<'PYTHON'
import hashlib
import os
import sys

paths = [line.strip() for line in sys.stdin if line.strip()]
paths.sort()

hasher = hashlib.sha256()
for path in paths:
  rel_path = os.path.relpath(path)
  hasher.update(rel_path.encode())
  with open(path, "rb") as handle:
    for chunk in iter(lambda: handle.read(8192), b""):
      hasher.update(chunk)

print(hasher.hexdigest())
PYTHON
)

if [[ "${BUILD_FORCE}" != "true" ]] && [[ -f "${BUILD_STAMP_PATH}" ]]; then
  previous_hash=$(cat "${BUILD_STAMP_PATH}")
  if [[ "${previous_hash}" == "${current_hash}" ]]; then
    echo "Build inputs unchanged; skipping uv build."
    exit 0
  fi
fi

mkdir -p "$(dirname "${BUILD_STAMP_PATH}")"

build_args=()
if [[ -n "${BUILD_ARGS}" ]]; then
  read -r -a build_args <<<"${BUILD_ARGS}"
fi

uv build "${build_args[@]}"

echo "${current_hash}" > "${BUILD_STAMP_PATH}"
