# Render Loop Surface Copy Optimization

## Technical problem

The render loop converted the rendered `pygame.Surface` into a Pillow image, then
rebuilt a new `pygame.Surface` from that Pillow image before blitting it to the
screen. This duplicated buffer copies every frame and added unnecessary per-frame
allocation work in `heart.environment.GameLoop._one_loop`.

## Change summary

- The loop now blits the renderer-produced `pygame.Surface` directly to the screen.
- The Pillow conversion is still performed, but only for the device image path.

## Materials

None.
