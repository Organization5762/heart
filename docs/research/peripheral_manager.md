# Peripheral Manager Detection Notes

The `PeripheralManager` (`src/heart/peripheral/core/manager.py`) centralizes detection and
lifecycle management for every runtime peripheral. Understanding its flow is helpful when
introducing new input devices or sensors.

## Detection pipeline

The manager builds its registry by iterating several detection helpers. Order matters because
switches set up a "main" switch fallback before any other peripherals are registered.

1. **Switches** – On a Raspberry Pi without X11 forwarding the manager asks both
   `Switch.detect()` and `BluetoothSwitch.detect()` for hardware handles. When no
   hardware is present it logs a warning and falls back to `FakeSwitch.detect()`. Non-Pi
   environments always use the fake switch path, ensuring development machines can test
   mode transitions without hardware.
1. **Sensors** – `Accelerometer.detect()` surfaces motion data sources.
1. **Gamepads** – `Gamepad.detect()` integrates joystick-style controllers.
1. **Heart rate monitors** – `HeartRateManager.detect()` aggregates pulse sensors under a
   single manager instance.
1. **Phone text** – `PhoneText.detect()` enables remote text input (via websocket polling
   or whatever transport the implementation supports).

Each detected object is appended to `self._peripherals` for later retrieval. The first switch
registered is cached as a deprecated "main switch" to support older APIs while still using
`PeripheralManager` as the single entry point.

## Threaded execution

Calling `start()` spins a daemon thread per peripheral. Each thread invokes the peripheral's
`run()` method. The manager tracks every thread for graceful shutdown: `close()` walks the
thread list and joins any active thread with a configurable timeout, reporting failures via
structured logging.

## Adding a new peripheral

When introducing a new peripheral type:

1. Implement a class that satisfies the `Peripheral` interface and provides a `detect()`
   classmethod returning an iterable of instances.
1. Extend `_iter_detected_peripherals()` (or a helper like `_detect_sensors()`) to yield the
   new objects.
1. Provide a dedicated accessor (similar to `get_gamepad()` or `get_phyphox_peripheral()`)
   if other subsystems need the device.
1. Consider how the peripheral should behave on developer machines. Supplying a "fake"
   implementation lets contributors exercise code paths without specialized hardware.

Following this pattern keeps peripheral discovery deterministic and ensures new devices plug
into the existing threading and lifecycle controls.
