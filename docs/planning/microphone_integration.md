# Microphone Peripheral Integration Plan

## Problem Statement

Deliver a microphone peripheral that streams normalised loudness metrics into the Heart runtime so rendering and program layers can react to ambient audio without destabilising deployments lacking capture hardware or optional dependencies.

## Materials

- Development host with a functional microphone and audio loopback tools for validation.
- Optional headless Linux target or container to verify graceful degradation paths.
- Access to the `sounddevice` library and ALSA/CoreAudio bindings as applicable.
- Source references: `src/heart/peripheral/core/manager.py`, `src/heart/peripheral/base.py`, `src/heart/runtime/events.py`.

## Opening Abstract

We will extend the peripheral manager to host a microphone device that continuously samples audio input, derives RMS and peak amplitude values, and publishes those metrics via the central event bus. The plan covers capability detection, runtime lifecycle, and validation so that lack of audio hardware simply disables the feature without disrupting other peripherals. Deliverable artefacts include a reusable peripheral module, configuration toggles, and documentation for runtime operators.

## Success Criteria

| Target behaviour | Validation signal | Owner |
| --- | --- | --- |
| Peripheral registers automatically when audio capture is supported. | Heart runtime logs show microphone attachment and emits `peripheral.microphone.level` events during smoke tests. | Runtime maintainer |
| Metric stream remains stable under intermittent audio spikes. | Automated tests simulate buffers with dynamic ranges and confirm bounded RMS/peak outputs. | Peripheral engineer |
| Deployments without audio hardware skip activation cleanly. | Integration test on headless container reports informational warning without raising exceptions. | Release engineering |

## Task Breakdown Checklists

### Discovery

- [ ] Catalogue supported audio backends from `sounddevice.query_devices()` per platform.
- [ ] Audit `PeripheralManager` to confirm lifecycle hooks for background threads.
- [ ] Review event bus payload schemas in `src/heart/runtime/events.py`.

### Implementation

- [ ] Implement `heart.peripheral.microphone.Microphone` inheriting from the common peripheral base class.
- [ ] Add a streaming loop that computes RMS and peak amplitude per buffer with configurable window length.
- [ ] Inject the runtime event bus using `attach_event_bus` and publish `peripheral.microphone.level` messages.
- [ ] Extend `PeripheralManager` registration to gate activation behind capability detection.
- [ ] Document configuration flags in `docs/library/tooling_and_configuration.md`.

### Validation

- [ ] Unit-test buffer processing helpers using prerecorded fixtures.
- [ ] Add a regression test ensuring absence of `sounddevice` triggers a warning rather than an exception.
- [ ] Capture manual run logs verifying metrics in the developer devlog.
- [ ] Update `docs/library/runtime_systems.md` with a summary of the new peripheral.

## Narrative Walkthrough

Discovery focuses on mapping the runtime entry points and understanding existing peripheral patterns so the microphone slot follows established contracts. Implementation threads the new peripheral class into the manager: upon startup the peripheral checks whether `sounddevice` can access an input device, spawns a background consumer that normalises audio blocks, and surfaces metrics through the event bus. Validation combines automated simulations of audio buffers with manual smoke tests on machines with and without microphones, ensuring the system degrades to a no-op when capture fails.

## Visual Reference

| Flow Step | Component | Notes |
| --- | --- | --- |
| Capability detection | `Microphone.detect_support()` | Queries `sounddevice` and configuration overrides. |
| Stream scheduling | `Microphone.start()` | Starts a daemon thread pulling audio buffers. |
| Metric emission | `Microphone._publish_levels()` | Sends RMS/peak payloads to the shared event bus. |
| Consumer handling | Renderers / programs | Subscribe to `peripheral.microphone.level` events. |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| `sounddevice` missing or incompatible backend. | Medium | Medium | Wrap import in optional extra and fall back to disabled state with warning. | Startup logs include dependency error messages. |
| Background thread overconsumes CPU on low-power devices. | Low | Medium | Permit configurable sample rate and buffer size, expose throttle defaults. | Runtime monitoring shows elevated CPU usage after activation. |
| Event bus flooding when audio is noisy. | Low | Medium | Rate-limit publishes and aggregate metrics before emission. | Metrics queue length grows or logging indicates dropped events. |
| Unit tests flaky due to timing-sensitive loops. | Medium | Low | Factor processing into pure functions and mock timeouts. | CI logs show intermittent timeouts around audio fixtures. |

### Mitigation Checklist

- [ ] Add configuration flags for sample rate, chunk size, and activation toggle.
- [ ] Ensure warnings surface through the runtime diagnostics channel.
- [ ] Document CPU utilisation expectations in the release notes.
- [ ] Provide developer tooling for replaying recorded audio fixtures.

## Outcome Snapshot

Once complete, the Heart runtime automatically provisions a microphone peripheral when hardware and dependencies exist. Operators see stable loudness metrics in event consumers, configuration knobs for tuning sampling parameters, and clean fallbacks when audio support is absent. The change lays groundwork for future spectral analysis while remaining safe to deploy across heterogeneous devices.
