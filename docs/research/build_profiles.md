# Build profiles for packaging workflows

## Summary

Packaging builds already cache work when inputs are unchanged, but developers
still need to remember which environment variables to set when they want faster
iteration or a specific build configuration. A named build profile adds a
single, memorable switch that bundles inputs, hash modes, and build arguments so
teams can align on the same settings and switch quickly between them.

## Materials

- `uv` for `uv build` execution.
- Python 3.11+ for parsing the profile configuration.
- `scripts/build_profiles.json` as the profile catalog.

## Sources

- `scripts/build_package.sh` (profile parsing, build hashing, manifest updates)
- `scripts/build_profiles.json` (profile definitions)
- `docs/library/tooling_and_configuration.md` (build helper documentation)

## Observations

- Build customization currently relies on multiple environment variables that
  are easy to forget or mistype during local iteration.
- Metadata hashing is a useful speed lever, but it is not obvious to new
  contributors when to enable it.

## Proposal

- Introduce named build profiles stored in a JSON catalog so developers can
  switch build configurations with a single `BUILD_PROFILE` value.
- Capture the chosen profile in the build manifest to make build decisions
  auditable and easier to reproduce.

## Expected impact

- Faster onboarding because common build setups are named and documented.
- Less configuration churn during iterative development when switching between
  strict and fast build modes.

## Follow-up ideas

- Add a `scripts/show_build_profile.sh` helper to print the active profile and
  effective settings.
- Extend profiles with optional documentation links or minimum tool versions.
