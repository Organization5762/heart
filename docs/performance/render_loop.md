# Render Loop Surface Copy Optimization

## Technical problem

The render loop converted the rendered `pygame.Surface` into a Pillow image, then
rebuilt a new `pygame.Surface` from that Pillow image before blitting it to the
screen. This duplicated buffer copies every frame and added unnecessary per-frame
allocation work in `heart.environment.GameLoop._one_loop`.

Renderer processing also allocated a full-size `pygame.Surface` for every
renderer on every frame. That created repeated allocations for each renderer
stack, even when renderer output sizes did not change.

When multiple renderers run together, surface composition relied on in-place
blitting into the first renderer's surface. That approach limited batching
opportunities and made it harder to adopt alternative merge strategies.

## Change summary

- The loop now blits the renderer-produced `pygame.Surface` directly to the screen.
- The Pillow conversion is still performed, but only for the device image path.
- Renderer processing reuses per-renderer screen surfaces when
  `HEART_RENDER_SCREEN_CACHE` is enabled (default on) to reduce per-frame
  allocations in `heart.environment.GameLoop.process_renderer`.
- Renderer composition in the iterative render path can use a cached composite
  surface and batched blits when `HEART_RENDER_MERGE_STRATEGY=batch` (default),
  while `HEART_RENDER_MERGE_STRATEGY=inplace` preserves the original merge
  behavior.

## Materials

None.
