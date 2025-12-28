# Runtime game loop modularization note

## Context

The runtime loop and rendering helpers have grown in scope inside
`src/heart/environment.py`. This change separates the runtime orchestration
(`GameLoop`, renderer variant selection) from HSV/BGR conversion utilities so
that runtime services and rendering helpers stay focused and easier to reuse.

## Materials

- Local checkout of this repository.
- Source references listed below.

## Findings

- `GameLoop` and `RendererVariant` now live in `src/heart/runtime/game_loop/core.py`.
  `src/heart/environment.py` is a compatibility shim that re-exports the runtime
  symbols for legacy imports.
- HSV/BGR conversion helpers and the conversion cache moved to
  `src/heart/utilities/color_conversion.py`, keeping the conversion helpers
  available as shared utilities outside the renderer layer.
- Modules that configure or record the runtime loop now import
  `heart.runtime.game_loop` directly, which makes the entry points explicit and
  reduces the dependency surface of the environment shim.

## References

- `src/heart/runtime/game_loop/core.py`
- `src/heart/utilities/color_conversion.py`
- `src/heart/environment.py`
- `src/heart/display/recorder.py`
- `src/heart/loop.py`
