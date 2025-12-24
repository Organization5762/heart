#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DIST_DIR=${DIST_DIR:-"${REPO_ROOT}/dist"}
PYPI_REPOSITORY_URL=${PYPI_REPOSITORY_URL:-}
PYPI_REPOSITORY=${PYPI_REPOSITORY:-}
PYPI_TOKEN=${PYPI_TOKEN:-}
TWINE_USERNAME=${TWINE_USERNAME:-}
TWINE_PASSWORD=${TWINE_PASSWORD:-}

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required to publish. Install it and try again." >&2
  exit 1
fi

publish_args=()
if [[ -n "${PYPI_REPOSITORY_URL}" ]]; then
  publish_args+=(--repository-url "${PYPI_REPOSITORY_URL}")
elif [[ -n "${PYPI_REPOSITORY}" ]]; then
  publish_args+=(--repository "${PYPI_REPOSITORY}")
fi

if [[ -n "${PYPI_TOKEN}" ]]; then
  : "${TWINE_USERNAME:=__token__}"
  : "${TWINE_PASSWORD:=${PYPI_TOKEN}}"
fi

if [[ -z "${TWINE_PASSWORD}" ]] && [[ ! -f "${HOME}/.pypirc" ]]; then
  echo "Error: missing credentials. Set PYPI_TOKEN or TWINE_PASSWORD, or configure ~/.pypirc." >&2
  exit 1
fi

"${REPO_ROOT}/scripts/build_package.sh"

if [[ ! -d "${DIST_DIR}" ]]; then
  echo "Error: dist directory not found at ${DIST_DIR}." >&2
  exit 1
fi

shopt -s nullglob
artifacts=("${DIST_DIR}"/*.whl "${DIST_DIR}"/*.tar.gz)
shopt -u nullglob

if [[ ${#artifacts[@]} -eq 0 ]]; then
  echo "Error: no distribution artifacts found in ${DIST_DIR}." >&2
  exit 1
fi

export TWINE_USERNAME
export TWINE_PASSWORD

uv tool run twine upload --non-interactive "${publish_args[@]}" "${artifacts[@]}"
