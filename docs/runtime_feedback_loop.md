# Recursive Input and Output Flow

## Overview

This note summarises how the runtime stitches together peripheral inputs, virtual sensors, and rendering loops into a feedback structure. The flow highlights how physical sensors feed an event bus, virtual definitions distil higher-order gestures, and game loops both consume and emit events so that downstream processors (such as ambient colour samplers) can reuse rendered frames.

## Physical Inputs to the Shared Bus

`PeripheralManager` discovers hardware, starts each device on a background thread, and wires them into a shared `EventBus` whenever propagation is enabled. The manager keeps track of both physical peripherals and virtual definitions so that everything publishes into the same queue. 【F:src/heart/peripheral/core/manager.py†L30-L168】

## Virtual Sensors Collapse Raw Signals

Higher-level gestures are implemented as `VirtualPeripheralDefinition` instances. Helpers such as `double_tap_virtual_peripheral`, `simultaneous_virtual_peripheral`, and `sequence_virtual_peripheral` register factories that listen for raw inputs, evaluate temporal predicates, and emit aggregated events back onto the bus. This lets configuration collapse noisy sensor streams into concrete actions. 【F:src/heart/peripheral/core/event_bus.py†L1010-L1094】

## Rendering Loops Emit Feedback

The primary `GameLoop` attaches the `PeripheralManager` to the same event bus, initialises an `LEDMatrixDisplay` peripheral, and registers it so rendered frames are published just like any other input. Every frame, the loop blits renderer output to the pygame surface, forwards it to the active device, and asks the LED matrix peripheral to emit a `peripheral.display.frame` payload. External consumers can then read those frames via the event bus or the peripheral’s `latest_frame` property. 【F:src/heart/environment.py†L263-L734】【F:src/heart/peripheral/led_matrix.py†L19-L111】

Renderer-specific state can also be observed directly. For example, the Mario renderer shares a `MarioRendererState` stream from `heart/renderers/mario/provider.py`, allowing diagnostics or companion effects to subscribe to sprite timing and acceleration thresholds without inspecting the renderer internals. 【F:src/heart/renderers/mario/provider.py†L1-L150】

## Recursive Flow Diagram

```mermaid
flowchart LR
    subgraph PhysicalInputs[Physical Inputs]
        Switches[Switch / BluetoothSwitch]
        Gamepads[Gamepads]
        Sensors[Accelerometer / Compass / Phyphox]
        HeartRate[Heart Rate]
        PhoneText[Phone Text]
    end

    subgraph PeripheralCoordination[PeripheralManager Threads]
        Manager[Register + attach\nEventBus]
        VirtualDefs[Virtual Peripheral Definitions]
    end

    subgraph EventFabric[EventBus + StateStore]
        Bus[Event Dispatch]
        Snapshots[Snapshots / Playlists]
    end

    subgraph RuntimeLoop[GameLoop]
        AppCtrl[AppController Modes]
        Renderers[Renderer Stack]
        Device[Device.set_image]
    end

    subgraph DisplayFeedback[LEDMatrixDisplay Peripheral]
        LedPublish[publish_image()<br/>peripheral.display.frame]
        Downstream[Derived Loop / Ambient Sampler]
    end

    Switches --> Manager
    Gamepads --> Manager
    Sensors --> Manager
    HeartRate --> Manager
    PhoneText --> Manager

    Manager -->|raw events| Bus
    VirtualDefs -->|aggregated events| Bus
    Bus -->|state snapshots| AppCtrl
    AppCtrl --> Renderers --> Device
    Renderers -->|frame surfaces| LedPublish
    Device -->|final image| LedPublish
    LedPublish -->|DisplayFrame events| Bus
    Bus -->|frame metrics| Downstream
    Downstream -->|optional commands| Bus
```

## Extensibility Notes

Because the LED matrix peripheral emits frames through the same event bus that carries physical input, additional game loops or analytics jobs can subscribe to `peripheral.display.frame` and compute statistics (for example an average pixel value) without touching the primary renderer. This keeps the architecture beautifully recursive: outputs become inputs for the next loop, and everything remains observable through the shared bus.
