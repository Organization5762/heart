# Doppler Renderer Notes (credit: Sri)

## Overview

The `heart.display.renderers.doppler.renderer.DopplerRenderer` simulates a 3D particle
field and maps the direction of motion to a red/blue hue gradient. The effect is
inspired by the Doppler shift, so particles moving toward the viewer shift
blue, while particles moving away trend red.

## Simulation loop

- The renderer initialises `particle_count` positions uniformly inside a cube of
  side length `2 × field_radius` and random velocities capped by `max_speed`.
- Each frame draws a Gaussian random acceleration for every particle, integrates
  the velocity, and applies reflective boundaries along X/Y/Z.
- Acceleration is recomputed from the change in velocity over the elapsed frame
  time (derived from `pygame.time.Clock.get_time`). A small guard keeps the
  integration stable when the reported frame delta is zero.

## Colour mapping

- Direction vectors are normalised and projected onto the camera Z-axis to
  estimate Doppler shift. The component value in `[-1, 1]` becomes a hue in the
  `[0, hue_extent]` range, interpolating red (0) to blue (`2/3`).
- The HSV value channel scales with acceleration magnitude so rapidly changing
  particles appear brighter. Saturation increases with acceleration but never
  drops below 0.3 to avoid washed-out tones.
- Colours convert to RGB via a vectorised HSV→RGB helper to keep the loop
  Numpy-friendly.

## Projection and rendering

- Particles project using a simple perspective model with a configurable focal
  length and camera distance. X coordinates adjust for the target surface aspect
  ratio to preserve symmetry across layouts.
- The renderer targets `DeviceDisplayMode.FULL` so each surface blit receives
  the full composition. Each visible particle draws as a small circle, giving a
  subtle glow without relying on post-processing.

## Extension points

- Update `_random_acceleration` to incorporate live sensor data (for example,
  `peripheral_manager.get_accelerometer()`) so real-world motion perturbs the
  particle field.
- Increase particle density by enabling `FrameAccumulator` support; the effect is
  currently CPU-bound by per-pixel drawing rather than the physics integration.
- Swap the linear hue ramp with a physically-derived spectral mapping if a
  richer colour split is desired.
