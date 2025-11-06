# Compass Peripheral Plan

## Goals

- Provide real-time heading data derived from the LIS2MDL magnetometer that ships with the sensor bus firmware.
- Expose a high-level Python API for other runtime components to query the latest heading and raw magnetic field vector.
- Keep the design modular so future work can add tilt compensation, calibration, and persistence without large refactors.

## Current Constraints

- The accelerometer peripheral exclusively owns the USB serial connection to the KB2040 sensor bus.
- Magnetometer readings are already available on the microcontroller, but the firmware does not currently forward them to the host.
- There is an event bus abstraction in `heart.peripheral.core.event_bus` but peripherals do not yet attach to it.

## Proposed Architecture

1. **Sensor bus event emission** – Teach the CircuitPython driver to emit `sensor.magnetic` payloads whenever the magnetometer vector changes meaningfully.
1. **Peripheral event propagation** – Extend `Peripheral` and `PeripheralManager` so that peripherals can publish payloads onto the shared event bus, allowing lightweight listeners to react without opening their own serial connections.
1. **Compass peripheral** – Implement a `Compass` peripheral that subscribes to `sensor.magnetic` events, stores a smoothed vector history, and exposes helpers like `get_heading_degrees()`.
1. **Testing** – Unit test the heading math and the event subscription behavior.

## Open Questions

- How should we handle calibration (offset/scale) data? Initial implementation will assume factory calibration and revisit later.
- Do we want to add tilt compensation using accelerometer data during the initial pass or leave it as a follow-up?
- What heuristics should drive smoothing? A deque with a small rolling average seems reasonable for a first iteration.

## Next Steps

1. Re-enable magnetometer emissions in `drivers/sensor_bus/code.py`.
1. Add event bus plumbing inside the peripheral core so hardware readers can forward payloads to listeners.
1. Implement the `Compass` peripheral with heading helpers and rolling averaging.
1. Wire detection into `PeripheralManager` and add unit coverage.
