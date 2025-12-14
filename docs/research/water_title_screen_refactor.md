# Water title screen renderer refactor

## Context

The water title screen previously bundled its state, timing, and drawing logic
into a single module. Aligning it with the Water and Life renderer structure
reduces coupling and allows the state updates to be driven by the shared
peripheral clocks instead of ad-hoc `time.time()` calls.

## Changes made

- Introduced `WaterTitleScreenState` in
  `src/heart/renderers/water_title_screen/state.py` to capture the wave
  offset.
- Added `WaterTitleScreenStateProvider` in
  `src/heart/renderers/water_title_screen/provider.py`, which advances
  the wave offset on every `game_tick` using the latest `pygame.Clock` delta.
- Moved rendering logic to
  `src/heart/renderers/water_title_screen/renderer.py`, keeping it
  focused on drawing with the provided state.
- Registered the provider with the dependency container so scenes can resolve
  the renderer without manual wiring.

## Materials

- `src/heart/renderers/water_title_screen/state.py`
- `src/heart/renderers/water_title_screen/provider.py`
- `src/heart/renderers/water_title_screen/renderer.py`
- `src/heart/renderers/water_title_screen/__init__.py`
