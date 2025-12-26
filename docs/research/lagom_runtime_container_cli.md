# Lagom runtime container usage in CLI

## Problem statement

The CLI command responsible for launching the runtime constructed a
`ConfigurationRegistry` directly, which bypassed the Lagom container used for
other runtime services. This left the registry outside of the shared dependency
injection flow and made it harder to override or trace configuration lookup in
tests.

## Materials

- `lagom` container bindings from `src/heart/runtime/container.py`.
- CLI entry points in `src/heart/cli/commands/`.

## Change summary

- Register `ConfigurationRegistry` in the runtime container so it can be
  resolved alongside other runtime services.
- Build the runtime container before resolving the configuration registry and
  `GameLoop`, ensuring the CLI uses a single Lagom-backed resolver.

## Affected modules

- `src/heart/runtime/container.py`
- `src/heart/cli/commands/game_loop.py`
- `src/heart/cli/commands/run.py`
