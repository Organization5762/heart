# Render Loop Surface Copy Optimization

## Technical problem

The render loop converted the rendered `pygame.Surface` into a Pillow image, then
rebuilt a new `pygame.Surface` from that Pillow image before blitting it to the
screen. This duplicated buffer copies every frame and added unnecessary per-frame
allocation work in `heart.environment.GameLoop._one_loop`.

Renderer processing also allocated a full-size `pygame.Surface` for every
renderer on every frame. That created repeated allocations for each renderer
stack and obscured which render settings were still live versus which were
left over from older composition experiments.

## Change summary

- The loop now blits the renderer-produced `pygame.Surface` directly to the screen.
- The Pillow conversion is still performed, but only for the device image path.
- The current runtime keeps only the active composition knobs:
  `HEART_RENDER_CRASH_ON_ERROR` and `HEART_RENDER_TILE_STRATEGY`.

## Materials

None.
