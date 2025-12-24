# Renderer Screen Surface Cache

## Context

`heart.runtime.game_loop.GameLoop.process_renderer` previously allocated a full-sized
`pygame.Surface` for every renderer on every frame. The allocation cost scales
with the number of renderers, and it happens even when the display size stays
constant between frames. The cache adds a reusable surface per renderer so the
frame loop can clear and reuse buffers instead of allocating each time.

## Notes

- `Configuration.render_screen_cache_enabled` reads `HEART_RENDER_SCREEN_CACHE`
  to toggle reuse behaviour at runtime.
- `GameLoop._get_renderer_surface` keys cached surfaces by renderer instance,
  display mode, and device size to avoid sharing buffers across renderers.

## Source references

- `src/heart/runtime/game_loop.py` (`GameLoop._get_renderer_surface`,
  `GameLoop.process_renderer`)
- `src/heart/utilities/env.py` (`Configuration.render_screen_cache_enabled`)

## Materials

None.
