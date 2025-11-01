# Runtime Code Flow

The diagram below summarizes how a `totem run` invocation moves through the CLI, runtime loop, peripherals, and display devices. It highlights where the system crosses service boundaries such as hardware peripherals and external LED drivers.

```mermaid
flowchart LR
    %% Visual classes for different service categories
    classDef orchestrator fill:#1d4ed8,stroke:#1d4ed8,color:#f8fafc,stroke-width:2px;
    classDef service fill:#0f172a,stroke:#0f172a,color:#f8fafc;
    classDef input fill:#0369a1,stroke:#0369a1,color:#f8fafc;
    classDef output fill:#7c3aed,stroke:#7c3aed,color:#f8fafc;

    subgraph Launch["Launch & Configuration Services"]
        direction TB
        CLI["CLI (Typer `totem run`)"]
        Registry["Configuration Registry"]
        Configurer["Program Configuration\n`configure(loop)`"]
    end

    subgraph Runtime["GameLoop Orchestration"]
        direction TB
        Loop["GameLoop Service\n(start + main loop)"]
        AppRouter["AppController / Mode Router"]
        ModeServices["Mode Services & Renderers"]
        FrameComposer["Frame Composer\n(surface merge + timing)"]
    end

    subgraph Inputs["Peripheral & Signal Services"]
        direction TB
        PeripheralMgr["PeripheralManager\n(background threads)"]
        Switch["Switch / BluetoothSwitch"]
        Gamepad["Gamepad"]
        Sensors["Accelerometer / Phyphox"]
        HeartRate["HeartRateManager"]
        PhoneText["PhoneText"]
    end

    subgraph Outputs["Display & Device Services"]
        direction TB
        DisplaySvc["Display Service\npygame.display.flip"]
        LocalScreen["LocalScreen Window"]
        Capture["Frame Capture\n(share surface)"]
        DeviceBridge["Device Bridge"]
        LedMatrix["LEDMatrix Driver\n(rgbmatrix)"]
    end

    CLI --> Registry --> Configurer --> Loop
    Configurer --> AppRouter
    Loop --> AppRouter
    Loop --> FrameComposer
    AppRouter --> ModeServices --> FrameComposer --> DisplaySvc
    DisplaySvc --> LocalScreen
    DisplaySvc --> Capture --> DeviceBridge --> LedMatrix

    Loop --> PeripheralMgr
    PeripheralMgr --> Switch --> AppRouter
    PeripheralMgr --> Gamepad --> AppRouter
    PeripheralMgr --> Sensors --> AppRouter
    PeripheralMgr --> HeartRate --> AppRouter
    PeripheralMgr --> PhoneText --> AppRouter

    class CLI,Registry,Configurer,ModeServices,FrameComposer service;
    class Loop,AppRouter orchestrator;
    class PeripheralMgr,Switch,Gamepad,Sensors,HeartRate,PhoneText input;
    class DisplaySvc,LocalScreen,Capture,DeviceBridge,LedMatrix output;
```

## Rendering the diagram

Run `scripts/render_code_flow.py` to regenerate the SVG using the service layout encoded in this repository whenever the architecture changes:

```bash
python scripts/render_code_flow.py --output docs/code_flow.svg
```

The renderer no longer relies on the mermaid CLI; it generates the SVG directly so that styling stays consistent across environments.
