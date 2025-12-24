# Render Loop Surface Copy Optimization

## Technical problem

The render loop converted the rendered `pygame.Surface` into a Pillow image, then
rebuilt a new `pygame.Surface` from that Pillow image before blitting it to the
screen. This duplicated buffer copies every frame and added unnecessary per-frame
allocation work in `heart.environment.GameLoop._one_loop`.

Renderer processing also allocated a full-size `pygame.Surface` for every
renderer on every frame. That created repeated allocations for each renderer
stack, even when renderer output sizes did not change.

Compositing renderer layers also relied on repeated per-surface `blit` calls
even when a batched `blits` call would reduce Python overhead.

## Change summary

- The loop now blits the renderer-produced `pygame.Surface` directly to the screen.
- The Pillow conversion is still performed, but only for the device image path.
- Renderer processing reuses per-renderer screen surfaces when
  `HEART_RENDER_SCREEN_CACHE` is enabled (default on) to reduce per-frame
  allocations in `heart.environment.GameLoop.process_renderer`.
- The renderer stack merge step can use a batched `blits` call when
  `HEART_RENDER_MERGE_STRATEGY=blits`, or fall back to the original per-surface
  loop when `HEART_RENDER_MERGE_STRATEGY=loop`.

## Materials

None.
