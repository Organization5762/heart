#!/usr/bin/env bash

harness_command_exists() {
  command -v "$1" >/dev/null 2>&1
}

harness_require_file() {
  local path=$1

  if [[ ! -f "$path" ]]; then
    echo "Error: expected to find ${path}" >&2
    return 1
  fi
}

harness_collect_missing_commands() {
  local -n missing_ref=$1
  shift
  local cmd

  for cmd in "$@"; do
    if ! harness_command_exists "$cmd"; then
      missing_ref+=("$cmd")
    fi
  done
}

harness_report_optional_commands() {
  local cmd

  for cmd in "$@"; do
    if harness_command_exists "$cmd"; then
      echo "Optional tool available: ${cmd}"
    else
      echo "Optional tool missing: ${cmd}"
    fi
  done
}

harness_report_tool_versions() {
  local cmd

  for cmd in "$@"; do
    if ! harness_command_exists "$cmd"; then
      continue
    fi

    case "$cmd" in
      rsync)
        echo "Tool version: $(rsync --version | head -n 1)"
        ;;
      uv)
        echo "Tool version: $(uv --version)"
        ;;
      *)
        echo "Tool version: $("$cmd" --version | head -n 1)"
        ;;
    esac
  done
}
