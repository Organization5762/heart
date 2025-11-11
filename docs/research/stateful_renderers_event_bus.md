# Event-driven state updates for renderer inputs

## Overview

Stateful renderers previously polled `PeripheralManager` on each frame to
hydrate their internal snapshots. `FreeTextRenderer` queried
`PeripheralManager.get_phone_text()` for the most recent BLE message while
`MarioRenderer` called `PeripheralManager.get_accelerometer()` to check the
current acceleration vector. Both patterns contradicted the push-based
model used by `SwitchStateConsumer` and forced renderers to hold live
references to peripherals during rendering.

## Changes

- Added `AccelerometerConsumer` under
  `src/heart/display/renderers/internal/accelerometer.py` to cache the last
  `AccelerometerVector` published on the event bus and expose a
  `latest_acceleration()` helper for renderers.
- Updated `MarioRenderer` (`src/heart/display/renderers/mario.py`) to
  inherit the new mixin, subscribe to accelerometer updates during
  `initialize()`, and drive loop transitions from cached vectors instead of
  polling the manager each frame.
- Taught `FreeTextRenderer` (`src/heart/display/renderers/free_text.py`) to
  subscribe directly to `PhoneTextMessage` events, cache the latest text, and
  drop its stored `PhoneText` peripheral reference.

## Impact

Renderers rely solely on cached event-driven state during `process()`,
eliminating per-frame calls to `PeripheralManager`. Subscriptions are
established during `initialize()` and cleaned up in `reset()`, mirroring the
pattern already in place for switch state consumers.
