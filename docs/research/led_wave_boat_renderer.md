# LED Wave Boat Renderer

## Overview

The `LedWaveBoat` renderer (`src/heart/display/renderers/led_wave_boat.py`) turns live
accelerometer readings into a small wave simulation and keeps a pixel-scale boat
riding along the crest. The module keeps the device in `MIRRORED` mode so each
64×64 face can display identical water motion.【F:src/heart/display/renderers/led_wave_boat.py†L12-L37】

## Acceleration Mapping

- **Amplitude** – The combined magnitude of the X and Y axes expands the wave
  amplitude up to ~22% of the display height, producing higher chop as the device
  moves faster.【F:src/heart/display/renderers/led_wave_boat.py†L108-L135】
- **Baseline** – The Z component shifts the mean water level so tilting the unit
  fore/aft makes the water rise or fall under the boat.【F:src/heart/display/renderers/led_wave_boat.py†L122-L129】
- **Phase Speed** – Horizontal acceleration advances the primary wave phase,
  while the Y axis modulates a secondary ripple that keeps the surface lively even
  with subtle motion.【F:src/heart/display/renderers/led_wave_boat.py†L131-L140】
- **Boat Position** – The X axis eases the boat across the horizon, keeping the
  hull centred when the device is level and sliding toward the tilt when moved.【F:src/heart/display/renderers/led_wave_boat.py†L142-L155】

## Visual Elements

- **Water Columns** – Each column is redrawn from crest to seafloor using a deep
  blue fill with foam tint proportional to the local slope, emphasising the wave
  curvature.【F:src/heart/display/renderers/led_wave_boat.py†L170-L190】
- **Boat Sprite** – A fixed 5×4 pixel sprite combines hull, deck, mast, and sail
  pixels. The sail leans with the computed sway value so tilting the device rolls
  the boat visually.【F:src/heart/display/renderers/led_wave_boat.py†L66-L102】
- **Spray Particles** – When the keel dips into a rising wave the renderer emits
  six short-lived spray particles that arc upward and fade, matching the crest
  position for the splash.【F:src/heart/display/renderers/led_wave_boat.py†L57-L64】【F:src/heart/display/renderers/led_wave_boat.py†L156-L169】

## Runtime Characteristics

- The renderer advances at 60 FPS using `clock.tick_busy_loop(60)` to match the
  rest of the water-themed scenes.【F:src/heart/display/renderers/led_wave_boat.py†L192-L199】
- Particle updates apply simple gravity and damping to reduce per-frame cost
  while keeping a smooth spray arc.【F:src/heart/display/renderers/led_wave_boat.py†L40-L56】

## Limitations

- Without a registered accelerometer the renderer falls back to a calm sea by
  assuming gravity aligned with +Z, so test runs on desktop hardware stay stable.【F:src/heart/display/renderers/led_wave_boat.py†L44-L55】
- The wave generation is purely sinusoidal; there is no fluid simulation or
  conservation of momentum, so aggressive motions can produce visually impossible
  crests. Further work could integrate a lightweight shallow-water solver like
  the one used in `water_cube` for richer dynamics.
