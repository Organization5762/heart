# Farmhouse-Nautical Cloth Renderer

The `ClothSailRenderer` (`src/heart/display/renderers/cloth_sail.py`) draws a
256×64 OpenGL scene that spans the four panels of the cube layout without
mirroring adjacent faces. The fragment shader implements a simple cloth model
whose displacement is driven directly in GLSL so that the motion remains smooth
even on low-powered hosts.

## Rendering pipeline

- The renderer requests `DeviceDisplayMode.OPENGL`, compiles a pass-through
  vertex shader, and executes the cloth simulation inside a fragment shader.
- The shader models the sail as a surface parameterised by UV coordinates. It
  computes an anchored lean term so that the left edge tucks downwind while the
  right edge billows out. Travelling sine waves and low-frequency gust noise are
  layered to produce wind-driven motion.
- Surface normals are estimated by sampling the height field in the shader. The
  normals feed a single directional light and a grazing-term highlight so that
  folds read clearly across the full width of the cube.
- After each draw call the renderer reads back the RGB buffer with
  `glReadPixels` and blits it into the provided Pygame surface so downstream
  components can stream pixels to hardware.

## Visual design

The palette is limited to weathered sailcloth colours to match the farmhouse and
nautical brief: faded canvas bands, navy stripes, and rope-coloured hems on the
outer edges. The shader keeps a shallow sea-toned background near the borders so
the cloth reads as a hanging banner rather than a fullscreen overlay.

## Usage

Add the renderer to a loop with the `cloth_sail` configuration:

```
uv run heart --configuration cloth_sail
```

The loop registers the renderer via
`src/heart/programs/configurations/cloth_sail.py`.
