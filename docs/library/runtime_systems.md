# Runtime Systems

## Problem Statement

Describe how the Heart runtime composes configuration modules, loops, and peripherals so
engineers can extend the system without reverse engineering the control flow.

## Runtime Topology

- **Configuration registry**: `heart.programs.registry.ConfigurationRegistry` scans
  `heart.programs.configurations` for `configure(loop: GameLoop)` callables and runs the
  selected configuration from `totem run`.
- **Game loop**: `heart.runtime.game_loop.GameLoop` owns the pygame window, timing, and mode
  transitions. It wires renderers through the `AppController` and bridges peripherals via
  `heart.runtime.peripheral_runtime.PeripheralRuntime`.
- **Device targets**: Implementations of `heart.device.Device` (such as
  `heart.device.local_screen.LocalScreen` and `heart.device.rgb_display.LEDMatrix`) translate
  pygame surfaces into physical outputs.

## Renderer Scheduling

Configuration modules typically:

- Call `loop.add_mode(<label or renderer>)` to register a selectable mode.
- Use `mode.resolve_renderer(loop.context_container, RendererClass)` to construct renderers via
  dependency injection.
- Compose renderers with `heart.navigation.ComposedRenderer` or rotate them with
  `heart.navigation.MultiScene`.

## Peripheral Event Flow

- `heart.peripheral.core.manager.PeripheralManager` discovers hardware, starts each device on a
  background thread, and owns the shared input controller and profile services.
- `heart.peripheral.core.input.frame.FrameTickController` publishes one timing snapshot per loop,
  which renderer providers now consume directly.
- `heart.peripheral.core.input.keyboard.KeyboardController` and
  `heart.peripheral.core.input.gamepad.GamepadController` expose reusable input views that
  logical profiles build on.
- `heart.peripheral.core.input.debug.InputDebugTap` records raw, view, logical, and frame
  emissions so tests and runtime diagnostics can trace input flow without a synchronous event bus.

## Feedback Frames

Rendered frame outputs still remain observable through runtime composition and display services,
but input tracing is now handled through `InputDebugTap` rather than the deleted shared input
event bus.

## Metrics and Logging

- Use `heart.runtime.render.pipeline.RenderPipeline` for render timing and pacing metadata.
- `heart.runtime.render.pacing.RenderLoopPacer` supports adaptive loop timing when
  `HEART_RENDER_LOOP_PACING_STRATEGY=adaptive` is set, bounded by
  `HEART_RENDER_LOOP_PACING_MIN_INTERVAL_MS` and utilization targets.
- Log sampling is coordinated through `heart.utilities.logging_control.get_logging_controller()`
  (see `docs/library/tooling_and_configuration.md`).

## ReactiveX Tuning

Reactive streams can be tuned with environment variables for debounce and buffer sizes. The
current tuning knobs live in the shared Rx utilities and affect controller, profile, and provider
pipelines that orchestrate runtime input and rendering.

## Related References

- `docs/books/getting_started.md` for setup and local execution.
- `docs/library/tooling_and_configuration.md` for configuration authoring and CLI wiring.
- `docs/code_flow.md` for a deeper call graph and subsystem map.
