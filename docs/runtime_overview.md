# Runtime overview

The Heart runtime is built around a pygame-powered game loop that streams
content to either a simulated window or the LED matrix wall. This document
explains how the major services interact and where to hook in new behavior for a
major release.

## High-level architecture

At startup the `totem` CLI wires together three primary subsystems:

1. **Configuration loader** – `heart.programs.registry.ConfigurationRegistry`
   discovers configuration modules under `heart/programs/configurations`. Each
   module exposes a `configure(loop: GameLoop)` function that mutates the loop
   with new modes, renderers, and playlists.
1. **Game loop orchestration** – `heart.environment.GameLoop` encapsulates the
   pygame window, timing, and peripheral integration. The loop owns the
   `AppController`, a router that handles scene transitions and renders composed
   surfaces.
1. **Device abstraction** – `heart.device.Device` implementations translate
   pygame surfaces into concrete display updates. `LocalScreen` targets desktop
   development while `LEDMatrix` (from `heart.device.rgb_display`) streams frames
   to the RGB matrix via the `rgbmatrix` bindings.

The code-flow diagram in [`docs/code_flow.md`](code_flow.md) visualizes these
relationships and the threads used to communicate with peripherals.

## Renderers and modes

Renderers implement `heart.display.renderers.BaseRenderer` (or a concrete
specialization) and draw into the pygame surface supplied by the runtime. A
configuration file typically:

- Calls `loop.add_mode(<name or renderer>)` to create a new selectable mode.
- Registers one or more renderers via `mode.add_renderer(...)`.
- Optionally wraps renderers in `heart.navigation.MultiScene` or
  `heart.navigation.ComposedRenderer` to build playlists and stacked overlays.

For example, `lib_2025.py` mixes ambient animations (`WaterCube`), interactive
scenes (`ArtistScene`), and text overlays. The default configuration also adds a
sleep mode for low-power intervals.

## Peripheral integration

Peripheral workers are instantiated by
`heart.peripheral.core.manager.PeripheralManager`. The manager spawns background
threads for:

- Bluetooth switches and controllers (`heart.peripheral.switch`,
  `heart.peripheral.gamepad`).
- Serial-connected sensors such as accelerometers (`heart.peripheral.uart`).
- Heart-rate monitors aggregated via `heart.peripheral.heart_rates`.

Each worker pushes events into the `AppController`, where they can trigger scene
changes, animations, or custom render logic. Scenes can subscribe to the shared
state exposed through helper modules like `heart.peripheral.heart_rates`.

## Display pipeline

Every frame follows the same rendering pipeline:

1. The active mode asks each renderer for a frame. Complex modes often combine
   multiple renderers via `ComposedRenderer` or `MultiScene`.
1. The resulting surface is passed to `heart.display.service.DisplayService`,
   which manages timing and double buffering to avoid tearing.
1. The `Device` implementation converts the surface into the final output. The
   local screen writes to a pygame window, whereas the LED matrix driver extracts
   raw pixel data and streams it over SPI.

The pipeline supports frame capture (`heart.device.bridge.DeviceBridge`) for the
peripheral sidecar and for streaming previews to remote observers.

## Extending the runtime

To add a new scene:

1. Implement a renderer under `heart/display/renderers/`. See `water_cube.py` or
   `kirby.py` for patterns that leverage numpy-based effects and sprite sheets.
1. Update an existing configuration module or create a new one under
   `heart/programs/configurations/` and expose a `configure(loop)` function.
1. Run `totem run --configuration <your-module>` to verify the scene locally.

New peripheral integrations should live under `heart/peripheral/`. They can
register event handlers with the `PeripheralManager` so that the runtime picks
them up automatically.

## Related tools

- [`docs/getting_started.md`](getting_started.md) – end-to-end setup guide.
- [`docs/program_configuration.md`](program_configuration.md) – deep dive into
  authoring and composing configuration modules.
- [`docs/hardware_debug_cli.md`](hardware_debug_cli.md) – command reference for
  the Typer-based hardware debugging suite.
