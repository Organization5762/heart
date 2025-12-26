# Pixelated Sun Transit Shader

## Problem

We need a shader that demonstrates how 3D lighting data can be quantized into a 2D pixel-art aesthetic. The renderer has to ray trace a sun and its interaction with a ground plane so that shadows and brightness shifts confirm the shader is using proper scene information rather than a flat gradient.

## Approach

- Added `PixelSunriseRenderer` under `src/heart/renderers/pixel_sunrise.py` to house the OpenGL program that drives the effect.
- The vertex shader draws a fullscreen quad, while the fragment shader performs analytic ray intersections for a moving sun sphere, a cylindrical obelisk, and the ground plane.
- Lighting uses lambertian and specular terms sourced from the computed sun direction, along with a binary shadow test against the obelisk to generate long ground shadows as the sun lowers.
- After shading, color channels are quantized and dithered, and screen coordinates are snapped to a coarse grid to emulate low-resolution pixel art output.

## Shader Details

- The sun's position is animated along an azimuth/altitude arc with `fract`-wrapped time so a continuous day cycle runs without restarts.
- The fragment shader provides `intersect_sphere`, `intersect_ground`, and `intersect_column` helpers to keep the analytic ray tracing readable.
- `column_shadow` measures whether the sun's light ray crosses the obelisk before it reaches the light source, which drives the moving ground shadow.
- Quantization uses six tone levels per channel plus a hashed dither value derived from the snapped pixel cell to avoid obvious banding when the sky gradient shifts.
- The sky gradient and sun halo react to the sun height so the palette naturally shifts between dawn and midday values.

## Using the Renderer

- Instantiate `PixelSunriseRenderer` inside a playlist or debugging harness that expects a `BaseRenderer` implementation.
- The renderer requests `DeviceDisplayMode.OPENGL` and uses `pygame._sdl2` when available to match the drawable pixel size to the window, so run it on a platform with OpenGL 2.1 support or better.
- No additional uniforms are required; the class updates time and resolution for you each frame.
- Launch `totem run --configuration pixel_sunrise_demo` to exercise the stock configuration that boots directly into the shader. The module lives at `heart/programs/configurations/pixel_sunrise_demo.py` and mirrors the integration notes in `docs/renderers/renderer_catalog.md`.

## Materials

- Python 3.11+
- PyOpenGL, pygame, and NumPy (already included in the project environment)
- GPU and drivers capable of OpenGL 2.1 fragment shaders
