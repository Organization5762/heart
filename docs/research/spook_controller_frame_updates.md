# Spook controller frame updates

## Problem

The spook mode animation stalls after initialization because game tick events
are emitted before the display clock is updated, so spritesheet providers do
not receive a usable clock delta during the tick-driven state updates.

## Update

- Emit the display clock update before the per-frame game tick so spritesheet
  providers can compute elapsed time from the latest clock in the same loop.
- Keep the tick cadence to one event per frame so reactive state updates remain
  consistent across renderers.

## Materials

- `src/heart/runtime/game_loop/__init__.py`
- `src/heart/renderers/spritesheet/provider.py`
- `src/heart/renderers/spritesheet_random/provider.py`
