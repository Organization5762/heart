# Heart Scene Bridge

## Problem Statement

Provide a minimal PyO3 package that can own scene-selection state outside Python so the main
`heart` runtime can incrementally move scene management, and later tensor-heavy orchestration,
into Rust.

## Materials

- Rust 1.86 or newer with Cargo.
- Python 3.11 for the target environment.
- `maturin` for local extension builds.
- Source files in `src/lib.rs`, `src/bin/stub_gen.rs`, and `python/heart_rust/`.

## Current Scope

The bridge currently exposes a single `SceneManagerBridge` class plus a `SceneSnapshot` value
object. The Python package is intentionally small: it is just enough to prove import wiring,
stub generation, and the first `heart.navigation.MultiScene` integration point.

## Development Notes

- Install the package into a project environment with the root optional extra: `uv sync --extra native`.
- Build the extension directly from this directory with `maturin develop`.
- Refresh the Rust-generated stubs with `cargo run --bin stub_gen`.
- `stub_gen` needs a linkable Python 3.11 runtime; unresolved `Py*` linker symbols mean the build can compile Rust but cannot link against Python yet.
