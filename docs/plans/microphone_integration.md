# Microphone Peripheral Integration Plan

## Problem Statement

Add a microphone peripheral that publishes normalised loudness metrics to the Heart runtime without disrupting environments lacking audio input hardware.

## Materials

- Access to `sounddevice` or equivalent audio capture library.
- Development machine with microphone hardware for validation.
- Peripheral manager hooks in `heart.peripheral.core.manager`.
- Event bus implementation used by other peripherals.

## Technical Approach

1. Implement a microphone peripheral that opens a streaming audio input device, computes RMS and peak amplitude per block, and exposes the latest values.
1. Integrate the peripheral with the event bus so renderers and programs can subscribe to sound-derived events.
1. Ensure detection gracefully degrades when audio hardware or libraries are absent.

## Design Overview

- **Peripheral runtime**: Implement `heart.peripheral.microphone.Microphone` using `sounddevice` when available. Publish `peripheral.microphone.level` events containing loudness metrics and retain the latest values for polling consumers.
- **Event bus wiring**: Extend `PeripheralManager` to pass the shared event bus into peripherals that expose `attach_event_bus`. Register the microphone immediately so background streams emit events without extra configuration.
- **Detection lifecycle**: Add detection logic during startup. Missing libraries or devices should produce informative logs and skip activation rather than raising exceptions.
- **Testing considerations**: Factor audio block processing into helpers for deterministic unit tests. Simulate audio chunks to validate metric calculations and event payloads. Cover detection behaviour when `sounddevice` is unavailable.

## Open Questions

- Should the peripheral expose optional raw PCM frames for advanced visualisations?
- Do we need spectral features (FFT, Mel energy) in the initial release or as follow-up work?
- Should `sounddevice` live in the default dependency set or an optional extra for hardware-enabled deployments?
