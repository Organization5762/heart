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

The bridge currently exposes `SceneManagerBridge`, `SceneSnapshot`, and a new
`SoftwareSceneBuffer` value type for CPU-backed scene composition. The Python package is still
intentionally small: it proves import wiring, stub generation, the first
`heart.navigation.MultiScene` integration point, and an incremental path away from direct
`pygame.Surface` calls in non-GPU renderers.

## Development Notes

- Install the package into a project environment with the root optional extra: `uv sync --extra native`.
- Build the extension directly from this directory with `maturin develop`.
- Refresh the Rust-generated stubs with `cargo run --bin stub_gen`.
- `SoftwareSceneBuffer` stores canonical RGBA bytes in CPU memory, accepts pygame-style
  `(width, height, channels)` arrays for `blit_array`, and can serialize those frames through
  `safetensors` for later persistence or interchange.
- `stub_gen` needs a linkable Python 3.11 runtime; unresolved `Py*` linker symbols mean the build can compile Rust but cannot link against Python yet.
