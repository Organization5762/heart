# Channel diffusion mode

This mode starts with a single white pixel centered on the display and iteratively redistributes the color channels to neighboring tiles.

## Update rule

- For each pixel, send its green component to the squares directly above and below.
- Send the blue component to the squares directly left and right.
- Send the red component to all diagonal squares.
- Reduce the originating pixel by half of its brightness (computed from the maximum channel value) before clipping negative values to zero.
- Clip any channel that would exceed 255 after aggregation.

The renderer operates on the full device surface so the redistribution covers the entire display.

## Implementation notes

The mode is implemented in `ChannelDiffusionRenderer` (`src/heart/renderers/channel_diffusion/renderer.py`). The renderer maintains a grid of RGB values, applies the redistribution with NumPy slicing, clips the accumulated values, and blits the result to the active surface. The program entry point is exposed through `channel_diffusion.configure` (`src/heart/programs/configurations/channel_diffusion.py`).
