# Display mode management for OpenGL renderers

## Problem

The runtime previously always created the pygame window with `pygame.SHOWN`. OpenGL renderers such as
`FractalRuntime` (`src/heart/renderers/three_fractal/renderer.py`) require `pygame.OPENGL | pygame.DOUBLEBUF`, so the OpenGL context would never initialize when the display flags stayed in the
shown mode.

## Solution

The game loop now resolves an active display mode from the selected renderers and asks the
`DisplayContext` to apply it before rendering. The display context wraps a
`DisplayModeManager` (`src/heart/runtime/rendering/display.py`) so the application can switch to
`DeviceDisplayMode.OPENGL` when any renderer requests it and fall back to `pygame.SHOWN` for other
renderers. See:

- `GameLoop._resolve_display_mode` and `GameLoop._one_loop` in
  `src/heart/runtime/game_loop/__init__.py`.
- `DisplayContext.ensure_display_mode` in `src/heart/runtime/display_context.py`.

## Materials

- Pygame display flags and window management (`pygame.display.set_mode`).
