# Renderer catalog

This catalog summarizes renderer-specific behavior, wiring, and prerequisites.
Each entry links to the relevant module so the renderer can be integrated into a
configuration without hunting through the tree.

## Table of contents

- [Pixel model renderer](#pixel-model-renderer)
- [Pixel sunrise renderer](#pixel-sunrise-renderer)
- [Porthole window renderer](#porthole-window-renderer)
- [Cloth sail renderer](#cloth-sail-renderer)
- [3D glasses renderer](#3d-glasses-renderer)
- [Dual output demo](#dual-output-demo)
- [Text renderer package layout](#text-renderer-package-layout)

## Pixel model renderer

**Module:** `src/heart/renderers/pixel_model.py`

`PixelModelRenderer` rasterizes a Wavefront OBJ mesh through OpenGL, quantizes
lighting into a fixed palette, and then scales the output to the target display
surface.

**Pipeline highlights:**

- Loads and recenters the OBJ mesh during `initialize()`.
- Uses a single shader pair to apply Lambert lighting, rim light, and a
  specular highlight before quantizing to a fixed number of tones.
- Reads pixels back to a NumPy buffer, then scales the surface if the drawable
  size does not match the display surface.

**Usage:**

```python
from heart.renderers.pixel_model import PixelModelRenderer
from heart.utilities.paths import docs_asset_path

renderer = PixelModelRenderer(
    model_path=docs_asset_path("models", "pixel_runner.obj"),
    target_rows=96,
    palette_levels=6,
)
```

**Materials:**

- Python 3.11+
- PyOpenGL, pygame, NumPy (provided by the project environment)
- A Wavefront OBJ asset with vertex positions and optional normals

## Pixel sunrise renderer

**Module:** `src/heart/renderers/pixel_sunrise.py`

`PixelSunriseRenderer` ray traces a sun, ground plane, and obelisk in a fragment
shader, then snaps the output to a coarse pixel grid for a pixel-art effect.

**Configuration:**

```bash
totem run --configuration pixel_sunrise_demo
```

The configuration lives in
`src/heart/programs/configurations/pixel_sunrise_demo.py` and registers a
single mode named "Pixel Sunrise Demo".

**Integration notes:**

- The renderer selects `DeviceDisplayMode.OPENGL`; the host must expose an
  OpenGL 2.1 context.
- When `pygame._sdl2` is available the renderer queries the drawable surface
  size to avoid stretching the quantized output.

**Materials:**

- Python 3.11+
- PyOpenGL, pygame, NumPy (provided by the project environment)
- GPU drivers that support OpenGL 2.1 fragment shaders

## Porthole window renderer

**Module:** `src/heart/renderers/porthole_window/renderer.py`

`PortholeWindowRenderer` draws a brass window frame and masks a city-and-roof
scene so the output reads like a porthole view.

**Pipeline highlights:**

- Requests `DeviceDisplayMode.FULL` to draw the entire framebuffer before
  layout tiling.
- Composes the sky, roof, skyline, and clouds on an off-screen surface.
- Applies a circular mask and glass reflections before blitting back to the
  primary surface.

**Configuration:**

```bash
uv run heart --configuration porthole_window
```

The configuration is defined in
`src/heart/programs/configurations/porthole_window.py`.

**Materials:**

- Python 3.11+
- pygame (provided by the project environment)
- A runtime that can load the configuration above

## Cloth sail renderer

**Module:** `src/heart/renderers/cloth_sail.py`

`ClothSailRenderer` draws a 256×64 OpenGL scene that spans the cube panels
without mirroring adjacent faces. The fragment shader simulates a cloth sail
with a wind-driven displacement field.

**Pipeline highlights:**

- Runs the cloth simulation entirely in the fragment shader.
- Samples the height field to estimate normals and light the sail.
- Reads back pixels with `glReadPixels` so downstream display drivers can stream
  the frame.

**Configuration:**

```bash
uv run heart --configuration cloth_sail
```

The loop registers the renderer in
`src/heart/programs/configurations/cloth_sail.py`.

**Materials:**

- Python 3.11+
- PyOpenGL and pygame (provided by the project environment)
- GPU drivers that support OpenGL 2.1 fragment shaders

## 3D glasses renderer

**Module:** `src/heart/renderers/three_d_glasses/renderer.py`

`ThreeDGlassesRenderer` remaps static imagery into a red/cyan anaglyph so the
left and right lenses see offset channel data. Frames advance on a configurable
cadence, letting LED glasses or similar filters create depth cues.

**Usage:**

```python
from heart.renderers.three_d_glasses import ThreeDGlassesRenderer

renderer = ThreeDGlassesRenderer([
    "gallery/left_panel.png",
    "gallery/right_panel.png",
])
```

**Configuration:**

```bash
totem run --configuration three_d_glasses_demo
```

The configuration lives in
`src/heart/programs/configurations/three_d_glasses_demo.py`.

**Materials:**

- Python 3.11+
- pygame (provided by the project environment)
- LED glasses or color-filtering hardware for the full anaglyph effect

## Dual output demo

**Modules:**

- `src/heart/device/single_led.py`
- `src/heart/peripheral/average_color_led.py`
- `src/heart/programs/configurations/dual_output_demo.py`

This demo mirrors the average color of the primary LED matrix onto a secondary
1×1 LED device. It is useful for validating multi-device fan-out behavior.

**Configuration:**

```bash
totem run --configuration dual_output_demo
```

**Materials:**

- Python 3.11+
- A primary LED matrix device
- A secondary 1×1 LED device or compatible controller

## Text renderer package layout

**Package:** `src/heart/renderers/text/`

The text renderer is split into focused modules so state, wiring, and rendering
remain isolated. The free text pipeline renders with the pixel font and disables
anti-aliasing to preserve crisp glyph edges on low-resolution displays.
The text renderer defaults to the same pixel font; font names that end in
`.ttf` load from assets while other names resolve through the system font
registry.

- `provider.py` builds `TextRenderingState` and wires the main switch
  subscription that updates state on rotations.
- `state.py` defines the dataclass that stores text, font configuration, and
  positional offsets, and lazily initializes the pygame font.
- `renderer.py` contains the rendering logic and uses the provider to
  initialize state before blitting text onto the display surface.

Import the renderer and its state from the package modules so dependencies stay
explicit in call sites.
