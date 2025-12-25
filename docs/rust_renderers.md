# Rust-backed renderers

## Problem

Python-only renderers can be limiting when you need tight loops or CPU-bound
routines that benefit from Rust. The runtime needs a straightforward way to
import renderer modules built as Rust-backed Python extensions without editing
`PYTHONPATH` for every run.

## Approach

Use `heart.renderers.import_rust_renderer` to import a compiled Rust module at
runtime. The helper uses `importlib` search APIs to locate extension modules
without mutating `sys.path`.

### Materials

- Rust toolchain (stable)
- A Python extension builder such as `maturin`
- A compiled renderer extension module (e.g., `librust_renderer.so`)

## Usage

1. Build your Rust renderer as a Python extension module.
1. Set `HEART_RUST_RENDERERS_PATH` to the directory containing the compiled
   extension (`.so`, `.pyd`, or `.dylib`). Use multiple paths separated by the
   OS path separator (e.g., `:` on Linux/macOS, `;` on Windows).
1. Import the module from your configuration or scene code:

```python
from pathlib import Path

from heart.renderers import import_rust_renderer

module = import_rust_renderer(
    "heart.renderers.rust_demo",
    search_paths=[Path("/opt/heart/rust_renderers")],
)
RustRenderer = module.RustRenderer
```

## Notes

- The Rust module must expose a Python class that follows the renderer
  expectations (e.g., implements the `StatefulBaseRenderer` lifecycle in its
  Python API surface).
- If you rely solely on `HEART_RUST_RENDERERS_PATH`, you can omit
  `search_paths` in the helper call.
