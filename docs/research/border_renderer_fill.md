# Border renderer fill optimization

## Technical problem

The border renderer in `src/heart/renderers/pixels/renderer.py` drew every border pixel
with nested `set_at` loops. That path executes per-pixel Python calls each frame, which
adds overhead during render updates.

## Change summary

Use `Surface.fill` with rectangular regions to draw the border in four operations.
`pygame` handles the pixel writes internally, reducing Python-level work while
keeping the same border output.

## Materials

- `src/heart/renderers/pixels/renderer.py`
