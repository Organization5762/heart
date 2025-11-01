# Runtime Code Flow

The diagram below summarizes how a `totem run` invocation moves through the CLI, runtime loop, peripherals, and display devices. It highlights where the system crosses service boundaries such as hardware peripherals and external LED drivers.

```mermaid
flowchart TD
    subgraph Launch["Launch & Configuration"]
        CLI[`totem run --configuration <name>`]
        Typer[`heart.loop.run()` Typer CLI]
        Registry["ConfigurationRegistry.get(name)"]
        ConfigFn["configure(loop) in heart.programs.configurations.*"]
    end

    subgraph Core["Core GameLoop Runtime"]
        LoopStart["GameLoop.start()\n(initializes once)"]
        InitScreen["_initialize_screen()\npygame surfaces + clock"]
        InitPeripherals["_initialize_peripherals()\nPeripheralManager.detect()/start()"]
        EventLoop["while running:\n_handle_events()\n_preprocess_setup()"]
        AppCtrl["AppController/GameModes\nselect active mode"]
        Renderers["Active renderers\nreturn pygame surfaces"]
        Compose["_render_fn()\nmerge surfaces"]
    end

    subgraph Inputs["Peripheral Threads & Signals"]
        PeripheralMgr["PeripheralManager\nbackground threads"]
        Switch["Switch/BluetoothSwitch"]
        Gamepad["Gamepad"]
        Sensors["Accelerometer / Phyphox"]
        HeartRate["HeartRateManager"]
        PhoneText["PhoneText"]
    end

    subgraph Display["Display & Device Output"]
        ScreenFlip["pygame.display.flip\n+ capture surface"]
        DeviceOut["Device.set_image(image)"]
        subgraph LocalDisplay["Local PC Display"]
            LocalScreen["LocalScreen\nscaled pygame window"]
        end
        subgraph LedHardware["RGB LED Hardware"]
            MatrixWorker["MatrixDisplayWorker thread"]
            LedMatrix["LEDMatrix (rgbmatrix driver)"]
        end
    end

    CLI --> Typer --> Registry --> ConfigFn
    Typer --> LoopStart
    LoopStart --> InitScreen
    LoopStart --> InitPeripherals
    InitPeripherals --> PeripheralMgr
    PeripheralMgr --> Switch
    PeripheralMgr --> Gamepad
    PeripheralMgr --> Sensors
    PeripheralMgr --> HeartRate
    PeripheralMgr --> PhoneText

    ConfigFn -->|adds modes/scenes| AppCtrl
    LoopStart --> EventLoop
    EventLoop --> AppCtrl
    AppCtrl --> Renderers --> Compose --> ScreenFlip --> DeviceOut
    DeviceOut --> LocalScreen
    DeviceOut --> MatrixWorker --> LedMatrix

    Switch --> AppCtrl
    Gamepad --> AppCtrl
    Sensors --> AppCtrl
    HeartRate --> AppCtrl
    PhoneText --> AppCtrl
```

## Rendering the diagram

Run `scripts/render_code_flow.py` to regenerate an SVG (or PNG/PDF via `--format`) from the mermaid source whenever the architecture changes:

```bash
python scripts/render_code_flow.py --output docs/code_flow.svg
```

If `mmdc` is not already installed, the script will fall back to using `npx @mermaid-js/mermaid-cli`.
