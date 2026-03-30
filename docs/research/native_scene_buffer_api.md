# Native Scene Buffer API

## Problem Statement

The renderer layer still treats `pygame.Surface` as both the drawing API and the storage format
for frame data. That makes it hard to move CPU scene composition into `heart_rust`, and it keeps
pygame-specific calls such as `surfarray.blit_array` spread across renderers that do not actually
need pygame until final presentation.

## Materials

- `rust/heart_rust/src/lib.rs`
- `rust/heart_rust/python/heart_rust/__init__.py`
- `src/heart/runtime/scene_buffer.py`
- `src/heart/runtime/display_context.py`
- `src/heart/renderers/tixyland/renderer.py`
- `src/heart/renderers/slide_transition/renderer.py`
- `src/heart/renderers/cloth_sail/renderer.py`

## Notes

The first step is a CPU-only scene contract that mirrors the pygame drawing calls the codebase
already depends on:

- `blit(source, dest=(0, 0), area=None, special_flags=0)`
- `blits(blit_sequence, doreturn=True)`
- `blit_array(array, dest=(0, 0))`
- `fill(color, rect=None, special_flags=0)`
- `get_size()`, `get_width()`, `get_height()`
- `to_pygame_surface()`

`src/heart/runtime/scene_buffer.py` defines that contract as `SceneCanvas` and provides two
implementations:

- `PygameSceneCanvas`, which wraps a plain `pygame.Surface`
- `NativeSceneCanvas`, which wraps `heart_rust.SoftwareSceneBuffer`

`SoftwareSceneBuffer` is intentionally CPU-oriented. It stores canonical RGBA bytes in Rust,
supports `blit`, `fill_rect_rgba`, and pygame-style `blit_array`, and serializes the frame buffer
through `safetensors`. That keeps the in-memory contract simple while making tensor export cheap
for later caching, snapshotting, or off-process transport.

The migration path is incremental:

1. Renderers stop reaching for `window.screen` and `pygame.surfarray.blit_array(...)` directly.
1. `DisplayContext` exposes `blit`, `blits`, and `blit_array` so existing renderers can move to a
   scene-like interface without changing their output model yet.
1. Scratch buffers can later be built with `build_scene_canvas(...)` instead of always allocating a
   raw `pygame.Surface`.
1. The pygame window remains the final presentation step through `to_pygame_surface()` or a final
   `blit` into the display surface.

This keeps non-GPU renderers compatible with the current runtime while giving `heart_rust` a
stable scene API that is no longer coupled to pygame internals.
