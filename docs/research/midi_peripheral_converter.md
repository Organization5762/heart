# MIDI Peripheral Converter Research Note

## Overview

This note investigates how to translate data produced by Heart peripherals into MIDI-compatible output streams and, reciprocally, how to ingest MIDI into the peripheral event bus. The converter will monitor the `EventBus` used by `PeripheralManager`, emit MIDI messages over configurable transports (hardware DIN, USB MIDI, or virtual ports), and optionally subscribe to MIDI inputs so that Heart subsystems can react to external controllers. The goal is to leverage the existing normalized `Input` dataclass so that any peripheral that already publishes events can drive external synthesizers or DAWs without bespoke glue code, while external MIDI rigs can influence automations inside Heart without writing new peripherals. 【F:src/heart/peripheral/core/event_bus.py†L22-L68】【F:src/heart/peripheral/core/manager.py†L20-L104】【F:src/heart/peripheral/core/__init__.py†L13-L56】

## Context

Heart devices already orchestrate multiple peripherals—switches, accelerometers, heart-rate monitors, and phone bridges—through a shared manager and event bus abstraction. The bus synchronously dispatches events and maintains a state snapshot for observers, making it a natural tap point for MIDI conversion. Today, no component converts those inputs into an industry-standard music control protocol. Bridging to MIDI unlocks downstream creative coding, allows hardware synthesizers to respond to biometric or gestural signals, and supports experimental biofeedback performances.

## Reference Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│ PeripheralManager.detect()  │        │   MIDI Converter Runtime     │
│  - Switch / Sensor threads  │        │  ┌────────────────────────┐  │
│  - EventBus attachments     │───────▶│  │ EventBus Subscriber    │  │
│  - Input(event_type, data)  │        │  └────────────┬───────────┘  │
└─────────────────────────────┘        │               │              │
                                       │        Mapping Engine        │
                                       │   (profiles, scaling, LFOs)  │
                                       │               │              │
                                       │     MIDI Message Encoder     │
                                       │         (Note/CC/SysEx)      │
                                       │               │              │
                                       │      Transport Adapters      │
                                       │    (USB, DIN, Virtual Port)  │
                                       └───────────────┴──────────────┘
                                                       │
                                                       │  MIDI In
                                       ┌───────────────▼──────────────┐
                                       │    MIDI Input Listener        │
                                       │  (parses & publishes events)  │
                                       └──────────────────────────────┘
```

The converter subscribes to the `EventBus`, enriches events with state history when necessary, evaluates mapping rules, and emits MIDI packets. Transport adapters abstract the physical or virtual output mediums. Symmetrically, a MIDI input listener attaches to the same transports, decodes inbound MIDI messages, and converts them into `Input` events so that other Heart components can act on external controllers.

## Data Inputs and Normalization

Peripherals already standardize payloads via the `Input` dataclass, which stores `event_type`, `data`, `producer_id`, and timestamps. Maintaining this format ensures compatibility with state snapshots and other subscribers. The converter should support two ingestion modes:

1. **Direct subscription** – Register once for all events (wildcard subscription) and filter internally. This keeps registration code minimal and ensures future peripherals are automatically eligible.
1. **Profile-scoped subscription** – Allow optional narrower subscriptions per mapping profile to reduce overhead when targeting specific event families (e.g., accelerometer axes only).

## Mapping Semantics (Event → MIDI)

Design goals for mapping engine:

- **Event-to-Message Templates** – Each mapping rule defines source event types, target MIDI message class (note on/off, control change, pitch bend, SysEx), channel, and value derivation expressions.
- **Stateful Interpretations** – Some conversions (e.g., note duration from button press) require tracking past events. Rely on the bus `StateStore` to retrieve last-seen data, avoiding redundant caches. 【F:src/heart/peripheral/core/event_bus.py†L22-L68】
- **Scaling and Quantization** – Provide utilities to scale sensor ranges into MIDI 0–127 range or 14-bit pitch bend values. Include optional quantization tables (e.g., mapping heart rate to musical scale degrees).
- **Temporal Modulation** – Introduce smoothing operators (moving average, exponential smoothing) and scheduled envelopes so jittery sensor data yields musically meaningful output.

## MIDI Message Strategy

Priority message types for initial release:

1. **Control Change (CC)** – Map continuous sensor readings (accelerometer, heart rate variability) to CC values for synth parameter modulation.
1. **Note Events** – Translate binary triggers (switches, gamepad buttons) into note on/off pairs with configurable pitch, velocity, and duration.
1. **Pitch Bend and Aftertouch** – Offer expressive control for axes or microphone amplitude envelopes.
1. **System Exclusive (SysEx)** – Reserve structure to push richer telemetry into compatible devices (e.g., sending full sensor state snapshots).

Implementation should reuse existing Python MIDI libraries (e.g., `mido`, `python-rtmidi`) or wrap ALSA/JACK interfaces directly when running on Raspberry Pi. Evaluate dependency footprint versus in-house serialization; external libraries accelerate development but add packaging considerations for the Heart runtime environment.

## MIDI Input Ingestion (MIDI → Event)

Enabling MIDI ingestion requires a complementary mapping pipeline:

- **Transport Listeners** – Reuse the output transports in input mode when possible (many libraries expose duplex ports). When hardware lacks bidirectional support (e.g., DIN-only output), allow separate input adapter registration.
- **Message Normalization** – Translate MIDI primitives into `Input` events with clear `event_type` semantics (`midi.note_on`, `midi.cc`, etc.) and payloads that include channel, controller, velocity, and timestamps. Piggyback on the same `Input` dataclass so downstream consumers remain unaware of the MIDI origin. 【F:src/heart/peripheral/core/__init__.py†L13-L56】
- **Profiled Routing** – Let operators declare routing tables that map inbound MIDI messages to existing virtual peripherals or automation hooks. For example, a control change can map to `VirtualSwitch` toggles or parameter adjustments in automation services.
- **Feedback Loops** – Prevent infinite feedback by tagging events derived from MIDI and providing configuration to suppress re-broadcast of identical messages back out. Consider storing recent outbound hashes to detect loops.

Input support extends the converter into a bridge that can host co-creative sessions: a DAW can trigger Heart light shows, while sensors continue to modulate synth parameters.

## Transport Considerations

- **USB MIDI (class-compliant)** – Likely the primary route; ensure the Heart device exposes endpoints recognized by host OS. Investigate `python-rtmidi` for cross-platform support.
- **5-pin DIN** – For standalone synthesizers, integrate a microcontroller or HAT that provides UART-to-MIDI conversion. Need to confirm GPIO pin availability and electrical isolation.
- **Virtual Ports** – For debugging on development machines, create virtual MIDI ports so DAWs can listen without additional hardware.

Each transport adapter should share a common interface (`open()`, `send(message)`, `receive(callback)`, `close()`) to enable runtime selection. Receiving should forward raw MIDI bytes to the input listener, which performs parsing and publishes normalized events on the bus.

## Performance and Reliability

- **Thread Safety** – EventBus callbacks run synchronously, so heavy MIDI processing must be offloaded to a worker queue to avoid blocking other peripherals. Introduce a lock-free ring buffer or use `queue.Queue` with a dedicated sender thread.
- **Backpressure** – If MIDI output falls behind, apply rate limiting or drop low-priority events to maintain responsiveness.
- **Error Handling** – Wrap transport sends with retries and degrade gracefully when adapters disconnect (e.g., USB cable unplugged).
- **Inbound Burst Control** – Throttle high-frequency MIDI input streams (e.g., dense controller data) and batch them into coarser event updates when downstream consumers cannot keep up. Extend metrics to observe inbound queue depth separately.

## Configuration and UX

Add configuration schema entries so operators can define mapping profiles via YAML or UI. Expose toggles to enable/disable converter, choose transport, adjust velocity scaling, and enable inbound MIDI routing with per-message mappings. Align configuration loading with existing `Configuration` helper used by the PeripheralManager. 【F:src/heart/peripheral/core/manager.py†L63-L107】

## Validation Strategy

- **Unit Tests** – Simulate `Input` events and assert generated MIDI bytes match expectations for multiple mapping scenarios.
- **Integration Tests** – Spin up a fake EventBus, register converter, and ensure peripheral detection + event emission lead to expected transport calls. Mirror the flow for inbound MIDI by injecting byte streams into the transport listener and verifying normalized `Input` events on the bus.
- **Hardware Loops** – Use loopback MIDI adapters or software synths (FluidSynth) to validate real-time responsiveness and absence of dropped events.

## Open Questions

1. **Dynamic Mapping Updates** – Should users be able to load new mappings at runtime? Requires hot-reloading and state migration.
1. **Clock Synchronization** – Determine whether converter should emit MIDI clock or follow an external clock. Synchronization affects note quantization and arpeggiator behavior.
1. **Security Considerations** – Evaluate whether exposing MIDI over network protocols (RTP-MIDI) introduces attack surface for control hijacking.
1. **Inbound Message Arbitration** – Decide how conflicting inbound MIDI commands (e.g., multiple controllers targeting same automation) are resolved. Options include last-write-wins, priority weighting, or dedicated automation ownership.

## Next Steps

- Prototype wildcard EventBus subscription and confirm throughput under typical peripheral load.
- Survey Python MIDI libraries for latency and deployment feasibility, including duplex (input/output) capabilities.
- Draft configuration schema and CLI for toggling mappings and defining inbound routing.
- Coordinate with hardware team about transport hardware feasibility, especially for DIN outputs and whether dedicated MIDI inputs are available.
- Prototype inbound message parsing to confirm `Input` normalization covers common controllers.
