# Keyboard input declarations for debugging

## Problem

Keyboard input snapshots exposed pressed/held flags without explicit event edges,
which made the FakeSwitch mapping harder to follow during debugging. Input
dependencies were also implicit for peripherals and observable providers, so it
was not obvious which upstream data each component expects.

## Notes

- Keyboard keys now emit explicit press/hold/release events, allowing the fake
  switch mapping to filter for clear press edges.
- Peripherals and observable providers declare their upstream inputs and carry
  references to the concrete event streams they listen to, improving traceability
  when inspecting runtime wiring.

## Materials

- None (software-only refactor).

## Sources

- `src/heart/peripheral/keyboard.py`
- `src/heart/peripheral/switch.py`
- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/providers/__init__.py`
- `src/heart/peripheral/providers/switch/provider.py`
- `src/heart/peripheral/providers/acceleration/provider.py`
