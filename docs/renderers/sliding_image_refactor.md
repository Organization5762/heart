# Renderer modularization update

## Summary

- Converted the `sliding_image` renderer into a provider/state/renderer trio so it aligns with the newer reactive renderer pattern.
- Removed legacy single-file renderer modules (`artist.py`, `kirby.py`, `l_system.py`, and the old `sliding_image.py`) now superseded by their modular counterparts to avoid ambiguous imports.

## Details

- `src/heart/renderers/sliding_image/` now contains:
  - `state.py` with immutable state objects for images and composed renderers.
  - `provider.py` that produces stream-driven state updates tied to the main game tick.
  - `renderer.py` that loads resources, wires providers, and renders frames.
- Container registration entries were added in `__init__.py` so dependency-injected builders resolve consistently.
- Removing the legacy files ensures imports like `heart.renderers.sliding_image` or `...artist` always resolve to the modular packages rather than the older monolithic implementations.

## Impact

- Modular renderers can now be wired the same way as the Water or Life implementations, simplifying reuse and future maintenance.
- Downstream configuration modules will consistently target the structured packages without risk of loading stale code.
