# Event-driven state updates for renderer inputs

## Overview

Stateful renderers previously polled `PeripheralManager` on each frame to
hydrate their internal snapshots. `FreeTextRenderer` queried
`PeripheralManager.get_phone_text()` for the most recent BLE message while
`MarioRenderer` called `PeripheralManager.get_accelerometer()` to check the
current acceleration vector. Both patterns contradicted the push-based
model provided by the switch subscription helpers and forced renderers to
hold live references to peripherals during rendering.

## Changes

- Added `BaseRenderer.register_event_listener()` so renderers declare their
  dependencies up front and receive callbacks once `ensure_input_bindings()`
  executes.
- Updated `MarioRenderer` (`src/heart/renderers/mario.py`) to use
  the new helper, cache accelerometer vectors, and drive loop transitions
  from cached data instead of polling the manager each frame.
- Taught `FreeTextRenderer` (`src/heart/renderers/free_text.py`) to
  register a listener for `PhoneTextMessage` events, cache the latest text,
  and drop its stored `PhoneText` peripheral reference.

## Impact

Renderers rely solely on cached event-driven state during `process()`,
eliminating per-frame calls to `PeripheralManager`. Subscriptions activate
when `ensure_input_bindings()` runs (from `initialize()` or `get_renderers()`)
and reuse the same mechanism as switch state caching.
