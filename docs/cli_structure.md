# CLI structure

## Technical problem

The CLI entrypoint previously mixed Typer wiring with command implementations, which made the
module harder to scan and reason about when adding new commands.

## Restructured layout

- `src/heart/loop.py` now focuses on Typer app setup and command registration.
- `src/heart/cli/loop_commands.py` contains the implementations for `run`, `update-driver`, and
  `bench-device`.

## Materials

- None.
