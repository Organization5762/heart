# Renderer refactor notes

Refactored the `RenderColor` and `RenderImage` implementations under `src/heart/display/renderers/` to match the provider/state/renderer structure used by the Life and Water modules.

## Changes

- `RenderColor` now uses `RenderColorStateProvider` (`color/provider.py`) to emit a static `RenderColorState` snapshot, keeping the color data isolated from rendering logic.
- `RenderImage` now relies on `RenderImageStateProvider` (`image/provider.py`) to load image assets and publish scaled frames whenever the window size updates, ensuring the renderer only blits ready-to-display frames.

These updates align simple renderers with the same separation of concerns as more complex modules, simplifying future maintenance and testing.
