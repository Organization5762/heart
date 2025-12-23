# Harness tool list guardrails for build/install helpers

## Problem statement

The Makefile install target assumes the harness tool list exists and is populated,
which can yield confusing errors if the file is missing or empty. The harness
check script also skips tool validation silently when the list is empty.

## Update summary

- Filter the harness tool list in the Makefile so comment lines are ignored.
- Emit a warning when the list is missing or empty and skip tool installs or
  checks explicitly.

## Source locations reviewed

- `Makefile`
- `scripts/check_harness.sh`
- `scripts/harness_tools.txt`

## Materials

- `bash`
- `make`
