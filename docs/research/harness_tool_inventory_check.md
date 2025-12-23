# Harness tool inventory check

## Problem

The harness check validated system commands but did not verify that the uv tool
install set matched what the Makefile expects. That gap meant format and check
steps could fail later if a required uv tool was missing.

## Approach

- Added a shared tool inventory file so the Makefile and harness checks reference
  the same uv tool list.
- Extended `scripts/check_harness.sh` to read that list and warn when uv tools
  are not installed.
- Updated the sync harness documentation to describe the new check.

## Materials

- `scripts/harness_tools.txt`
- `Makefile`
- `scripts/check_harness.sh`
- `docs/sync_harness.md`
