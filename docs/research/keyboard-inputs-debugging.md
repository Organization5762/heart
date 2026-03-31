# Keyboard input state and debug mappings

## Summary

- Reworked keyboard handling around one shared `KeyboardController` so raw key
  snapshots, key-state views, and logical profiles all consume the same source.
- Moved fake-switch and accelerometer-debug keyboard mappings out of ad hoc
  per-scene wiring and into shared logical profiles.

## Motivation

Debug tooling is more useful when every keyboard-derived behaviour can be traced
back to one controller. The rewrite keeps the detailed `KeyboardEvent` payloads,
but moves most consumers onto `KeyboardController` views so navigation,
accelerometer debugging, and Mandelbrot controls no longer each build their own
polling path.

## Implementation notes

- `heart.peripheral.core.input.keyboard.KeyboardController` owns keyboard
  snapshots plus shared `key_pressed`, `key_released`, `key_held`, and
  `key_state` views.
- `heart.peripheral.core.input.profiles.navigation.NavigationProfile` maps arrow
  keys to logical browse and activation outputs shared by `FakeSwitch`,
  `GameModes`, and `MultiScene`.
- `heart.peripheral.core.input.accelerometer.AccelerometerDebugProfile` maps
  `A/D`, `W/S`, `Q/E`, and `Space` onto a synthetic accelerometer vector for
  desktop debugging.
- `heart.peripheral.keyboard.KeyboardEvent` remains the low-level event payload
  for raw key edges and debug inspection.

## Materials

- Shared keyboard controller in `src/heart/peripheral/core/input/keyboard.py`.
- Navigation mappings in `src/heart/peripheral/core/input/profiles/navigation.py`.
- Debug accelerometer mappings in
  `src/heart/peripheral/core/input/accelerometer.py`.
- Compatibility keyboard event type in `src/heart/peripheral/keyboard.py`.
