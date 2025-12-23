# Renderer role audit: image and sliding renderers

## Problem

The renderer/state/provider split drifted in two packages. The image renderer provider scaled pixels instead of only updating state, and the sliding image/rendering paths advanced state inside render loops instead of letting providers own event-driven updates. This blurred responsibilities across files and made the state stream harder to reason about.

## Findings

- `RenderImageStateProvider` scaled images in response to window changes, which is rendering work rather than state construction.
- `SlidingImage` and `SlidingRenderer` advanced state directly during `real_process`, even though providers already define update logic.

## Adjustments

- The image provider now emits a base image plus window size, while `RenderImage` scales during `real_process` and caches the scaled surface.
- Sliding providers now combine the game tick with the window-size stream to advance offsets, so renderers only read state and draw.

## Materials

- `src/heart/renderers/image/provider.py`
- `src/heart/renderers/image/state.py`
- `src/heart/renderers/image/renderer.py`
- `src/heart/renderers/sliding_image/provider.py`
- `src/heart/renderers/sliding_image/state.py`
- `src/heart/renderers/sliding_image/renderer.py`
