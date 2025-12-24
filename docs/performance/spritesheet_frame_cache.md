# Spritesheet Frame Cache Strategy

## Technical problem

Spritesheet renderers were extracting a frame from the sheet and scaling it on
every tick. That meant repeated blits from the sheet to a new surface and
a repeated resize even when the frame and target size did not change. This
showed up across spritesheet-based renderers that use the same frame for several
frames of animation.

## Change summary

- Spritesheet frame extraction can now reuse cached frame surfaces instead of
  rebuilding them each tick.
- Optional scaled-frame caching eliminates repeated resizes for spritesheet
  renderers that draw the same frame size repeatedly.

## Configuration

- `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY=scaled` (default) caches both raw frame
  surfaces and scaled variants.
- `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY=raw` caches only the extracted frames
  and still scales each frame per tick.
- `HEART_SPRITESHEET_FRAME_CACHE_STRATEGY=off` disables caching for spritesheet
  frames.

## Materials

None.
