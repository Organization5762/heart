# Rx-first input/provider rewrite

## Problem Statement

Document the input rewrite that replaces mixed peripheral polling, switch-specific
navigation wiring, and provider-owned timing joins with layered controllers,
views, logical profiles, and a shared frame snapshot.

## Materials

- `src/heart/peripheral/core/input/debug.py`
- `src/heart/peripheral/core/input/frame.py`
- `src/heart/peripheral/core/input/keyboard.py`
- `src/heart/peripheral/core/input/gamepad.py`
- `src/heart/peripheral/core/input/accelerometer.py`
- `src/heart/peripheral/core/input/profiles/navigation.py`
- `src/heart/peripheral/core/input/profiles/mandelbrot.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/runtime/container/initialize.py`
- `src/heart/runtime/peripheral_runtime.py`
- `src/heart/navigation/game_modes.py`
- `src/heart/navigation/multi_scene.py`
- `src/heart/renderers/mandelbrot/control_mappings.py`
- `src/heart/renderers/mandelbrot/scene.py`
- `src/heart/renderers/mario/provider.py`
- `src/heart/renderers/led_wave_boat/provider.py`
- `src/heart/renderers/water_cube/provider.py`
- `src/heart/renderers/three_fractal/renderer.py`
- `tests/peripheral/test_input_core.py`
- `tests/runtime/test_container.py`

## Architecture

- `PeripheralManager` now owns shared input services instead of exposing a merged
  event bus.
- `InputDebugTap` records traced envelopes for raw, view, logical, and frame
  emissions so tests and runtime logging can follow lineage.
- `FrameTickController` emits one `FrameTick` snapshot per loop and becomes the
  canonical timing input for providers.
- `KeyboardController` and `GamepadController` own raw snapshots plus reusable
  key, button, axis, stick, and d-pad views.
- `NavigationProfile`, `MandelbrotControlProfile`, and
  `AccelerometerDebugProfile` map shared controller views into scene-friendly
  logical outputs.

## Migration outcomes

- Time-driven providers now consume `FrameTickController.observable()` instead of
  joining `game_tick` and `clock`.
- `FakeSwitch`, `GameModes`, and `MultiScene` now consume logical navigation
  streams rather than direct arrow-key subscriptions.
- Desktop accelerometer debugging for Mario, water, and boat scenes now routes
  through `AccelerometerDebugProfile`.
- Mandelbrot input mapping now reads from `MandelbrotControlProfile`, and the
  remaining direct keyboard polling in `three_fractal` now consumes shared
  keyboard and canonical gamepad snapshots.

## Operational notes

- The first observability surface is intentionally the debug tap only; there is
  no runtime UI for inspecting envelopes yet.
- `PeripheralManager.get_gamepad()` and `get_main_switch_subscription()` still
  exist as compatibility adapters, but new code should prefer the controller and
  profile services.
- Keyboard polling now degrades to an empty snapshot when pygame input is
  unavailable, which avoids background thread exceptions during teardown.
