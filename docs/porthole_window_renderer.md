# PortholeWindowRenderer

## Overview

`PortholeWindowRenderer` (`src/heart/display/renderers/porthole_window/renderer.py`)
draws a brass-framed porthole around the current device viewport. The renderer
builds the window frame directly in Pygame, masking an animated city-and-roof
scene so that the active output resembles looking outside through a ship's
porthole.

## Rendering pipeline

- The renderer requests `DeviceDisplayMode.FULL` so it can paint the entire
  framebuffer before the display layout performs any tiling.
- A radial drop shadow and multi-ring frame use successive `pygame.draw.circle`
  calls to approximate an aged brass housing with highlights and rivets.
- The outdoor view is composited on an off-screen `pygame.Surface`. A vertical
  gradient establishes the sky, the roof plane is drawn with two polygons and a
  shingle pass, and the skyline uses `pygame.Rect` fills for distant buildings.
- Cloud ellipses drift horizontally according to `sin` of the elapsed runtime
  streamed from the renderer's provider-managed state, keeping motion consistent
  across resets and warm-up cycles.
- After the scene is composed, a circular mask with `BLEND_RGBA_MULT` trims the
  surface before it is blitted back into the main framebuffer. Separate arcs add
  glass reflections on the primary surface to sell the curved glazing.

## Running the renderer

Launch the standalone configuration with:

```bash
uv run heart --configuration porthole_window
```

The configuration is defined in
`src/heart/programs/configurations/porthole_window.py` and registers a single
mode that installs `PortholeWindowRenderer` with its state provider.

## Materials

- Python 3.11+
- pygame (provided by the project environment)
- The standard Heart loop (`uv run heart`) or equivalent harness that loads the
  configuration module above
