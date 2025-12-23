# Random pixel renderer role separation

The random pixel renderer mixed responsibilities by generating pixel positions
and per-frame colors inside the renderer. That made the renderer own state
mutation instead of limiting it to drawing. The renderer has been adjusted so
pixel locations and color are emitted from the provider and stored in state,
while the renderer only turns that state into pixels.

## Notes

- `RandomPixelStateProvider` now subscribes to the game tick stream and emits
  updated pixel coordinates (and random colors when no fixed color is set).
- `RandomPixelState` stores the current pixel coordinates alongside the color
  for the frame.
- `RandomPixel` renders whatever coordinates and color are in state without
  computing new positions at draw time.

## Sources

- `src/heart/renderers/random_pixel/provider.py`
- `src/heart/renderers/random_pixel/state.py`
- `src/heart/renderers/random_pixel/renderer.py`
