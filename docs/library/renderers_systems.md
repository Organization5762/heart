# Renderers and Visual Systems

## Problem Statement

Summarize how renderer composition, refactors, and performance-related helpers fit together so
contributors can add or update visuals without scattering knowledge across multiple notes.

## Renderer Composition

- `heart.renderers.BaseRenderer` and its specializations supply the core render API.
- `heart.navigation.ComposedRenderer` stacks multiple renderers into a single frame.
- `heart.navigation.MultiScene` rotates renderer instances on a schedule.
- `heart.renderers.stateful` classes encapsulate renderer-specific state and are loaded through
  the runtime container to keep dependencies explicit.

## Refactor Notes

The renderer refactor effort focuses on:

- Moving orchestration logic out of renderers and into configuration modules.
- Consolidating renderer lifecycle hooks under shared base classes.
- Keeping stateful renderers in dedicated modules to reduce cross-cutting concerns.

Use the renderer catalog in `docs/renderers/renderer_catalog.md` to locate existing
implementations and `docs/renderers/base_class_layout.md` for inheritance layout.

## Rust Renderer Integration

Rust renderers are loaded through the search paths configured in
`heart.renderers.rust.loader`, which checks:

- `HEART_RUST_RENDERERS_PATH` when set.
- The default `/opt/heart/rust_renderers` path on deployment targets.

The loader expects each renderer bundle to expose its metadata alongside compiled artifacts.

## Spritesheet Cache

Spritesheets are cached through `heart.assets.sprite_cache`. Cache sizing and invalidation live
near the loader and should be tuned alongside renderer memory profiles.

## Related References

- `docs/library/rendering_experiments.md` for experimental renderer notes.
- `docs/library/tooling_and_configuration.md` for configuration patterns that compose renderers.
