# Runtime Overview

## Problem Statement

Explain how the Heart runtime composes configuration modules, orchestrates renderers, integrates peripherals, and targets display hardware so engineers can extend the system without reverse engineering the control flow.

## Materials

- Installed `heart` development environment.
- Access to the source modules referenced in this document.
- Familiarity with pygame concepts and threaded peripheral IO.

## Technical Approach

1. Describe startup orchestration across configuration loading, game loop management, and device abstraction.
1. Detail how renderers and modes cooperate to draw frames.
1. Document peripheral lifecycle hooks and the display pipeline to aid future integrations.

## High-Level Architecture

At startup the `totem` CLI builds three core subsystems:

1. **Configuration loader** – `heart.programs.registry.ConfigurationRegistry` inspects `heart/programs/configurations` for modules exposing `configure(loop: GameLoop)`. Each callable mutates the loop with modes, renderers, and playlists.
1. **Game loop orchestration** – `heart.environment.GameLoop` owns the pygame window, timing, and peripheral integration. Its `AppController` routes scene transitions and composes surfaces.
1. **Device abstraction** – Implementations of `heart.device.Device` translate pygame surfaces into concrete outputs. `LocalScreen` targets desktop iteration, while `LEDMatrix` in `heart.device.rgb_display` streams frames through the `rgbmatrix` bindings.

Refer to [code_flow.md](code_flow.md) for the full call graph and service boundaries.

## Renderers and Modes

Renderers extend `heart.renderers.BaseRenderer` (or a specialization) and draw into the surface supplied by the loop. Configuration modules typically:

- Call `loop.add_mode(<label or renderer>)` to register selectable modes.
- Attach renderers with `mode.resolve_renderer(loop.context_container, RendererClass)` to run them sequentially each frame while leveraging dependency injection.
- Wrap renderers in `heart.navigation.MultiScene` or `heart.navigation.ComposedRenderer` to control scheduling and overlays.

`lib_2025.py` demonstrates how to mix ambient animations (`WaterCube`), interactive scenes, and a low-power sleep mode managed through `loop.app_controller.add_sleep_mode()`.

## Peripheral Integration

`heart.peripheral.core.manager.PeripheralManager` spawns background threads for:

- Bluetooth switches and controllers (`heart.peripheral.switch`, `heart.peripheral.gamepad`).
- Serial-connected sensors (`heart.peripheral.uart`).
- Heart-rate monitors aggregated by `heart.peripheral.heart_rates`.

Workers push events into the `AppController`, which propagates state to renderers. Scene code can subscribe to helper modules such as `heart.peripheral.heart_rates` to retrieve the latest readings.

The game loop also registers a virtual `LEDMatrixDisplay` peripheral so each rendered frame is emitted as a `peripheral.display.frame` payload. Consumers that need access to the live output (for example, analytics or secondary displays) can subscribe to this event stream without coupling to the renderer stack.

## Display Pipeline

Each frame flows through the same stages:

1. The active mode asks its renderers for frames. Composite modes may layer results through `ComposedRenderer` or rotate them with `MultiScene`.
1. `heart.display.service.DisplayService` manages timing and double buffering to prevent tearing.
1. The chosen `Device` implementation emits the output. `LocalScreen` writes to a pygame window, whereas the LED matrix driver streams pixel rows over SPI. Optional capture paths such as `heart.device.bridge.DeviceBridge` share frames with auxiliary processes.
1. The `LEDMatrixDisplay` peripheral publishes the rendered frame and metadata so downstream subscribers can observe the runtime output.

## Extending the Runtime

To add a scene or peripheral:

1. Implement a renderer under `heart/renderers/` (see `water_cube.py` for reference).
1. Register it in an existing configuration module or introduce a new module in `heart/programs/configurations/` with `configure(loop)`.
1. Execute `totem run --configuration <module>` to validate behaviour.
1. For non-cube layouts, pass `--orientation rectangle --orientation-columns <cols> --orientation-rows <rows>` to override the default cube geometry.
1. Place new peripheral integrations under `heart/peripheral/` and register them with the `PeripheralManager` so the runtime activates them automatically.

## Related References

- [getting_started.md](getting_started.md) – environment preparation and deployment steps.
- [program_configuration.md](program_configuration.md) – authoring playlists and renderer compositions.
- [hardware_debug_cli.md](hardware_debug_cli.md) – Typer commands for hardware validation.
