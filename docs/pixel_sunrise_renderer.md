# PixelSunriseRenderer

## Overview

`PixelSunriseRenderer` ray traces a moving sun, ground plane, and obelisk
inside an OpenGL fragment shader before snapping colours to a coarse
pixel grid. The effect demonstrates how analytic lighting can feed a
pixel-art presentation without losing spatial cues.

## Running the demo

```bash
totem run --configuration pixel_sunrise_demo
```

The configuration lives in
`heart/programs/configurations/pixel_sunrise_demo.py`. It registers a
single mode named "Pixel Sunrise Demo" so the shader starts immediately
when the loop boots.

## Renderer integration notes

- The renderer selects `DeviceDisplayMode.OPENGL`, so ensure the target
  platform exposes an OpenGL 2.1 context.
- `PixelSunriseRenderer` manages its own time and resolution uniforms;
  no additional configuration parameters are required.
- When `pygame._sdl2` is available the renderer queries the drawable
  surface size to avoid stretching the quantised output.

## Materials

- Python 3.11+
- PyOpenGL, pygame, and NumPy (provided by the project environment)
- GPU drivers capable of OpenGL 2.1 fragment shaders
