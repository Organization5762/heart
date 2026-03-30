# Rx Input Services Guide

## Overview

Heart input now flows through shared Rx services owned by
`heart.peripheral.core.manager.PeripheralManager`:

- `FrameTickController` emits one `FrameTick` snapshot per loop.
- `KeyboardController` exposes shared keyboard snapshots and key views.
- `GamepadController` exposes canonical button, axis, stick, and d-pad views.
- Logical profiles such as `NavigationProfile`,
  `MandelbrotControlProfile`, and `AccelerometerDebugProfile` map those
  shared views into scene-friendly streams.
- `InputDebugTap` records raw, view, logical, and frame emissions for tests and
  runtime tracing.

## Publishing input

Peripheral implementations still publish through `Peripheral.observe`. The
controller layer subscribes to those peripheral streams or polls the relevant
pygame input source and exposes shared Rx observables above them. New features
should publish through the relevant peripheral or controller, not through a
global synchronous bus.

## Consuming input

1. Resolve the shared controller or profile from the runtime container.
1. Subscribe to the smallest stream that matches the use case.
1. Prefer logical profiles over device-specific views when the scene only cares
   about intent.

Examples:

- Navigation scenes subscribe to `NavigationProfile.browse_delta`,
  `activate`, and `alternate_activate`.
- Time-driven providers subscribe to `FrameTickController.observable()`.
- Desktop accelerometer debugging subscribes to
  `AccelerometerDebugProfile.observable()`.

## Tracing input flow

Use `InputDebugTap.observable()` or `InputDebugTap.snapshot()` to inspect traced
input envelopes. Each envelope records:

- `stage`
- `stream_name`
- `source_id`
- `timestamp_monotonic`
- `payload`
- `upstream_ids`

This is the supported debugging surface for following transitions such as
`keyboard.right -> navigation.browse_delta -> GameModes`.

## Testing

- Subscribe to controller or profile observables directly in unit tests.
- Use `InputDebugTap.snapshot()` to assert stage and lineage metadata.
- Prefer controller/profile stubs over reconstructing pygame polling in scene
  tests when the contract under test is logical input behaviour.
