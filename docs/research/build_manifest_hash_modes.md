# Build manifest and hash modes for package builds

## Summary

Packaging builds already skip repeated work when inputs are unchanged, but it was
hard to audit why a build ran or to tune hashing costs during local iteration.
The build wrapper now records a manifest for each decision and supports a
metadata hash mode to trade content scanning for faster stat-based hashing when
appropriate.

## Materials

- `uv` for `uv build` execution.
- Python 3.11+ for the build hashing and manifest writer.
- Optional `git` for file discovery.

## Sources

- `scripts/build_package.sh` (build hash logic, manifest writer, input handling)
- `docs/library/tooling_and_configuration.md` (environment variables for build helpers)

## Observations

- The build wrapper already maintains a stamp file, but the decision details were
  only visible in terminal output.
- Hashing full file contents can be slow in large workspaces or when sync loops
  trigger frequent checks.

## Proposal

- Emit a JSON manifest alongside the stamp so developers can inspect build
  inputs, hash mode, tool versions, and the reason a build ran or skipped.
- Introduce a hash mode toggle to let teams use metadata-only hashing when they
  need faster feedback during repetitive packaging cycles.

## Expected impact

- Faster local iteration when opting into metadata hashing on large workspaces.
- Easier troubleshooting because build decisions are preserved in a structured
  artifact.

## Follow-up ideas

- Capture average hash time in the manifest to quantify performance gains.
- Add a small CLI wrapper to print the latest manifest in a human-friendly
  format.
