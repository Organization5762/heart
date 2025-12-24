# Keyboard input state and debug mappings

## Summary

- Reworked keyboard event payloads to carry a single `KeyState` snapshot plus the
  key name so debug tooling can inspect a complete state transition in one
  object.
- Tightened input declarations for peripherals and observable providers so each
  descriptor exposes a filtered stream of exactly the input payload it consumes.

## Motivation

Debug tooling for fake peripherals benefits when keyboard events describe their
state transitions in a single payload, and when input descriptors already match
what downstream consumers handle. The new keyboard event structure now bundles
state alongside the action and key metadata, and the input descriptors for
`DrawingPad`, `FakeSwitch`, and observable providers only emit the payloads
those components consume.

## Implementation notes

- `heart.peripheral.keyboard.KeyboardEvent` now includes `key_name` and a single
  `KeyState` snapshot (`pressed`, `held`, `last_change_ms`).
- `heart.peripheral.switch.FakeSwitch` uses a dedicated key-press stream helper
  so input declarations and runtime subscriptions both consume pressed edges.
- `heart.peripheral.drawing_pad.DrawingPad` input descriptors now filter the
  event bus to the two supported event types and expose only the payloads.
- Observable providers return input descriptors that already unwrap or filter
  the peripheral envelopes into the payload type they advertise.

## Materials

- Pygame keyboard state polling (`pygame.key.get_pressed`) in
  `src/heart/peripheral/keyboard.py`.
- Input descriptor definitions in `src/heart/peripheral/core/__init__.py`.
- Fake switch keyboard mappings in `src/heart/peripheral/switch.py`.
