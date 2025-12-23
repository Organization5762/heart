# Spritesheet renderer state streams

## Problem

The spritesheet loop renderers were advancing their animation state inside
`real_process`, which mixed state updates with pixel output. This made it harder
to reason about event-driven timing and to keep the provider/state/renderer split
consistent across the renderers.

## Update

- Moved spritesheet loop state advancement into providers driven by the
  `PeripheralManager` event streams so renderers only read state and blit frames.
- `SpritesheetProvider` now emits state updates from game ticks and switch input.
- `SpritesheetLoopRandomProvider` owns frame metadata and timing progression to
  keep renderer logic focused on scaling and blitting.

## Materials

- `src/heart/renderers/spritesheet/provider.py`
- `src/heart/renderers/spritesheet/renderer.py`
- `src/heart/renderers/spritesheet_random/provider.py`
- `src/heart/renderers/spritesheet_random/renderer.py`
- `tests/display/test_spritesheet_loop_renderer.py`
