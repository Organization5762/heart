# Native Scene Bridge

## Problem Statement

Scene selection is still managed entirely in Python, which blocks incremental migration of
navigation state and later tensor-heavy scene orchestration into Rust.

## Materials

- `rust/heart_rust/Cargo.toml`
- `rust/heart_rust/src/lib.rs`
- `rust/heart_rust/src/bin/stub_gen.rs`
- `rust/heart_rust/python/heart_rust/__init__.py`
- `src/heart/navigation/native_scene_manager.py`
- `src/heart/navigation/multi_scene.py`
- `pyproject.toml`

## Notes

The new `rust/heart_rust` package uses a mixed maturin layout so Python shims and Rust
extension code stay in one place. `SceneManagerBridge` is intentionally narrow: it owns scene
names, button-offset resets, and active-scene index resolution, which is enough to replace the
current modulo arithmetic in `MultiScene` without forcing a larger renderer rewrite.

The root `heart` project now exposes the bridge through an optional `native` extra. Runtime code
continues to work without Rust by falling back to `PythonSceneManagerBridge` in
`src/heart/navigation/native_scene_manager.py`. That keeps the import surface stable while making
the Rust path available anywhere the environment installs `heart-rust`.
