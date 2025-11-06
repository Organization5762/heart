# Program Configuration Guide

## Problem Statement

Describe how to construct repeatable playlists of modes and renderers so the Heart runtime can be tailored to specific events or installations without modifying the core loop.

## Materials

- Local checkout of the repository with an activated development environment.
- Familiarity with `heart.programs.registry.ConfigurationRegistry` and the `GameLoop` APIs.
- Access to renderer implementations under `heart.display.renderers` and navigation helpers under `heart.navigation`.

## Technical Approach

1. Implement a module in `heart/programs/configurations/` that exposes `configure(loop: GameLoop) -> None`.
1. Register modes, compose renderers, and wire peripheral data sources through the provided navigation and renderer utilities.
1. Load the module via `totem run --configuration <name>` to validate the playlist locally and on target hardware.

## Registry Operation

`ConfigurationRegistry` loads configuration modules on demand. When `totem run --configuration lib_2025` executes, the CLI imports every module under `heart.programs.configurations`, records their exported `configure` callables, and invokes the selected entry with the live `GameLoop`. Any import failure surfaces immediately in the console so authors can correct missing dependencies.

## Minimal Module Example

```python
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    hello_mode = loop.add_mode("hello")
    hello_mode.add_renderer(
        TextRendering.default(text="Hello, world!", y_location=16)
    )
```

Important behaviours:

- `loop.add_mode(<label or renderer>)` registers a selectable mode. Pass a string for a simple label or a renderer that supplies its own title screen.
- `mode.add_renderer(...)` appends renderers that execute sequentially each frame, enabling overlays or layered effects.
- `loop.app_controller.add_sleep_mode()` inserts a low-power fallback. The CLI toggles this path with `--add-low-power-mode/--no-add-low-power-mode`.

## Building Playlists

Use `heart.navigation` helpers to manage scheduling:

- `MultiScene` rotates through renderers on a fixed cadence.
- `ComposedRenderer` stacks renderers to combine animations and overlays.

Example fragment from `lib_2025.py`:

```python
from heart.display.renderers.water_cube import WaterCube
from heart.display.renderers.water_title_screen import WaterTitleScreen
from heart.navigation import ComposedRenderer


def configure(loop: GameLoop) -> None:
    water_mode = loop.add_mode(
        ComposedRenderer([WaterTitleScreen(), TextRendering.default("water")])
    )
    water_mode.add_renderer(WaterCube())
```

## Integrating Peripheral Data

Peripherals publish readings through modules in `heart.peripheral`. Renderers can pull values directly, as shown below:

```python
from heart.peripheral.heart_rates import current_bpms


class HeartRateVisualization(BaseRenderer):
    def render(self, surface: pygame.Surface, *_: Any) -> None:
        bpm = current_bpms().average
        # Draw something based on bpm
```

Peripheral managers start with the loop, so configuration modules do not instantiate them manually.

## Validation Workflow

1. Place the new module in `heart/programs/configurations/` with a descriptive name such as `festival_2025.py`.
1. Launch it locally:
   ```bash
   totem run --configuration festival_2025
   ```
1. Iterate on renderers and scheduling. Use `--no-add-low-power-mode` if the playlist should loop continuously.

Watch for `Importing configuration:` log lines to confirm registry discovery. Commit auxiliary assets (sprite sheets, audio) alongside the module if they are required at runtime.

## Operational Guidance

- Store large assets under `src/heart/assets/` so they deploy with the package.
- Document hardware prerequisites in `docs/devlog/` or a README adjacent to the configuration if it depends on non-standard peripherals.
- Add targeted tests under `tests/` when configurations contain scheduling or state management logic that benefits from regression coverage.
