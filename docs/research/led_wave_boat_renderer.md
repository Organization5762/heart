# LED Wave Boat Renderer

## Overview

The `LedWaveBoat` renderer now mirrors the Water and Life modules by separating
state definition, frame updates, and drawing into distinct files under
`src/heart/renderers/led_wave_boat/`. The state provider combines window
geometry, clock deltas, and accelerometer readings into a shared
`LedWaveBoatState`, while the renderer focuses solely on turning that state into
pixels. The device remains in `MIRRORED` mode so each 64×64 face shares the same
animation.【F:src/heart/renderers/led_wave_boat/provider.py†L28-L78】【F:src/heart/renderers/led_wave_boat/renderer.py†L19-L21】

## Acceleration Mapping

- **Amplitude** – The combined magnitude of the X and Y axes expands the wave
  amplitude up to roughly a quarter of the display height so harder movement
  yields higher chop.【F:src/heart/renderers/led_wave_boat/state.py†L63-L75】
- **Baseline** – The Z component shifts the mean water level so tilting the unit
  fore/aft raises or lowers the sea relative to the boat.【F:src/heart/renderers/led_wave_boat/state.py†L63-L74】
- **Phase Speed** – Horizontal acceleration advances the primary wave phase,
  while the Y axis modulates a secondary ripple that keeps the surface lively
  even with subtle motion.【F:src/heart/renderers/led_wave_boat/state.py†L72-L88】
- **Boat Position** – The X axis eases the boat across the horizon, keeping the
  hull centred when the device is level and sliding toward the tilt when moved.【F:src/heart/renderers/led_wave_boat/state.py†L88-L95】

## Visual Elements

- **Water Columns** – Each column is redrawn from crest to seafloor using a deep
  blue fill with foam tint proportional to the local slope, emphasising the wave
  curvature.【F:src/heart/renderers/led_wave_boat/renderer.py†L88-L114】
- **Boat Sprite** – A fixed 5×4 pixel sprite combines hull, deck, mast, and sail
  pixels. The sail leans with the computed sway value so tilting the device rolls
  the boat visually.【F:src/heart/renderers/led_wave_boat/renderer.py†L35-L67】
- **Spray Particles** – When the keel dips into a rising wave the state factory
  emits six short-lived spray particles that arc upward and fade, matching the
  crest position for the splash.【F:src/heart/renderers/led_wave_boat/state.py†L96-L107】【F:src/heart/renderers/led_wave_boat/state.py†L178-L192】

## Runtime Characteristics

- The provider uses the latest clock delta to advance the simulation while the
  renderer reads the shared state without recalculating physics.【F:src/heart/renderers/led_wave_boat/provider.py†L28-L78】
- Particle updates apply simple gravity and damping to reduce per-frame cost
  while keeping a smooth spray arc.【F:src/heart/renderers/led_wave_boat/state.py†L152-L176】

## Limitations

- Without a registered accelerometer the state assumes gravity aligned with +Z,
  so desktop runs stay stable while still animating gentle waves.【F:src/heart/renderers/led_wave_boat/state.py†L119-L124】
- The wave generation is purely sinusoidal; there is no fluid simulation or
  conservation of momentum, so aggressive motions can produce visually impossible
  crests. Further work could integrate a lightweight shallow-water solver like
  the one used in `water_cube` for richer dynamics.【F:src/heart/renderers/led_wave_boat/state.py†L132-L150】
