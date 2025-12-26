# Build profile inspection helper

## Summary

Packaging builds are configurable through environment variables and profile
definitions, but it is not obvious which inputs, hash modes, or arguments are
active during local iteration. A lightweight inspection helper surfaces the
effective settings so developers can confirm build configuration before running
`uv build`.

## Materials

- Python 3.11+ for JSON parsing and environment handling.
- `scripts/build_profiles.json` for profile definitions.
- `scripts/show_build_profile.sh` for profile inspection.
- `make build-info` as the entry point for the helper.

## Sources

- `scripts/build_package.sh` (profile resolution and hashing logic).
- `scripts/build_profiles.json` (profile catalog).
- `scripts/show_build_profile.sh` (profile inspection output).
- `Makefile` (build-info target).
- `docs/library/tooling_and_configuration.md` (build helper documentation).

## Observations

- Contributors often rely on environment variables like `BUILD_HASH_MODE` and
  `BUILD_INPUTS`, which can lead to uncertainty about the active configuration.
- Build profiles are useful, but they were previously opaque without inspecting
  JSON or running a build.

## Implementation notes

- The inspection helper resolves the same defaults as the build script, including
  fallback to the `default` profile when a profile catalog exists.
- Output includes the source of each setting (environment variable, profile, or
  default), so overrides are clear during troubleshooting.

## Expected impact

- Faster iteration when switching between build profiles because developers can
  validate settings before executing packaging commands.
- Fewer configuration errors during sync and build workflows by making the
  active inputs and arguments explicit.
