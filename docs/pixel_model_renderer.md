# PixelModelRenderer

`PixelModelRenderer` converts standard Wavefront OBJ meshes into a pixel-art
rendering by rasterising them with OpenGL and quantising the lighting output.
It lives at `src/heart/renderers/pixel_model.py` and exposes the same
`BaseRenderer` lifecycle hooks as the existing shader-based renderers.

## Rendering pipeline

- The renderer loads an OBJ file once during `initialize()`, recentres it around
  the origin, and rescales it so the largest dimension fits inside a two-unit
  cube. Vertex normals from the file are used if present; otherwise flat normals
  are generated per face.
- A single vertex/fragment shader pair draws the model with per-fragment
  Lambert lighting, a small rim light, and a specular highlight. The fragment
  shader clamps the palette to six tones per channel, applies a blue-grey night
  ambient tint, and modulates the dither by snapping `gl_FragCoord` into coarse
  cells.
- Pixels are read back into a NumPy buffer after each frame. When the display
  surface size differs from the OpenGL drawable size, the resulting surface is
  scaled with `pygame.transform.smoothscale()` before presenting.

## Usage

```
from heart.renderers.pixel_model import PixelModelRenderer
from heart.utilities.paths import docs_asset_path

renderer = PixelModelRenderer(
    model_path=docs_asset_path("models", "pixel_runner.obj"),
    target_rows=96,
    palette_levels=6,
)
```

The mesh path accepts any OBJ file that supplies vertex positions. Normals are
optional. Larger models benefit from pre-computing normals so the shading stays
smooth after the renderer rescales the mesh.

The renderer maintains an orbiting camera to show the asset’s volume. Adjust the
palette density and pixel rows to match the target display characteristics. For
example, using `target_rows=48` exaggerates the chunky-pixel look when the host
screen is a high-resolution laptop display.

## Sample asset

`docs_asset_path("models", "pixel_runner.obj")` resolves a low-poly runner
silhouette that is already centred and scaled. Use it to validate the renderer
wiring before bringing in external assets.
