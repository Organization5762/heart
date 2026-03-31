# Peripheral Manager Detection Notes

## Problem Statement

Summarise how `PeripheralManager` discovers and manages devices so new peripherals integrate cleanly.

## Materials

- `src/heart/peripheral/core/manager.py` implementation.
- Access to representative hardware (switches, sensors, gamepads, heart-rate monitors, phone text bridge).
- Logging output from runtime startup.

## Technical Approach

1. Review the detection order and fallback rules that populate the manager registry.
1. Document the threading model and shutdown behaviour.
1. Outline the steps required to add a new peripheral type.

## Detection Pipeline

- Switches (`Switch`, `BluetoothSwitch`) register first, with `FakeSwitch` providing a fallback when hardware is absent.
- Motion sensors (`Accelerometer`) and other devices (gamepads, heart-rate monitors, phone text) follow, each appended to `self._peripherals`.
- Manager-owned controller services (`FrameTickController`, `KeyboardController`, `GamepadController`, and logical profiles) sit on top of the detected peripherals so downstream code consumes shared Rx services instead of a merged event bus.

## Threading Model

Calling `start()` launches a daemon thread per peripheral invoking its `run()` method. `close()` iterates the thread list, joins active workers with a timeout, and logs failures. This ensures controlled shutdown when the runtime exits.

## Adding a Peripheral

1. Implement the `Peripheral` interface with a `detect()` classmethod returning instances.
1. Extend `_iter_detected_peripherals()` (or a specialised helper) to yield the new devices.
1. Prefer exposing new shared controller or profile services instead of adding raw manager accessors; keep direct accessors such as `get_gamepad()` only for compatibility.
1. Supply a fake implementation for developer environments without hardware when feasible.

## Conclusion

Maintaining the detection order and thread lifecycle makes peripheral discovery deterministic and keeps the manager the single coordination point for input devices.
