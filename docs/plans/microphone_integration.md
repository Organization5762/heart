# Microphone Peripheral Integration Plan

## Objectives

- Provide a dedicated `Microphone` peripheral that captures audio input and exposes normalized loudness data to the rest of the Heart runtime.
- Stream audio-derived events through the shared peripheral event bus so renderers or programs can react to sound in real time.
- Keep the integration optional when audio backends are unavailable so development environments without microphones still function.

## Design Overview

1. **Peripheral runtime**
   - Implement `heart.peripheral.microphone.Microphone` that opens a streaming input device using the `sounddevice` module when available.
   - Compute lightweight metrics (RMS, peak amplitude) for each audio block and publish them as `peripheral.microphone.level` events.
   - Maintain the latest metrics on the instance for polling consumers that do not use the event bus.
1. **Event bus wiring**
   - Allow the `PeripheralManager` to propagate an attached `EventBus` instance to peripherals that expose an `attach_event_bus` hook.
   - Ensure the microphone peripheral registers with the event bus immediately when detected so the background stream can emit events without additional configuration.
1. **Detection lifecycle**
   - Add microphone detection to the manager so it becomes part of the standard peripheral startup sequence.
   - When `sounddevice` is missing or no input devices are available, detection should fail gracefully with an informative log message and no raised exception.
1. **Testing considerations**
   - Factor audio-block processing into an isolated helper to make the RMS/peak calculations testable without depending on physical microphones.
   - Add unit coverage that verifies detection behaviour when `sounddevice` is absent and that simulated audio chunks produce the expected event payload.

## Open Questions / Future Work

- Decide whether to expose raw PCM frames over a secondary event type for advanced audio visualizations.
- Explore downsampling or spectral feature extraction (FFT, Mel energy) once initial loudness-driven integrations land.
- Revisit dependency management to determine if `sounddevice` should be part of the default install or an optional extra for hardware-enabled deployments.
