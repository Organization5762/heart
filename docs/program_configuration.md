# Program configuration guide

Program configurations define the playlist of scenes, overlays, and behaviors
that run on the Heart totem. Each configuration is a Python module in
`heart/programs/configurations/` and must expose a single `configure(loop)`
function. This guide explains how the registry works and how to build your own
configuration for events or installations.

## Registry basics

`heart.programs.registry.ConfigurationRegistry` discovers configuration modules
on demand. When you run `totem run --configuration lib_2025` the CLI:

1. Imports `heart.programs.registry.ConfigurationRegistry`.
1. Loads every module under `heart.programs.configurations` and stores the
   `configure` callable in a dictionary keyed by the module name.
1. Retrieves the requested entry and executes it with the active
   `GameLoop` instance.

Any import errors are surfaced at startup so failures are easy to spot.

## Anatomy of a configuration module

A minimal configuration looks like this:

```python
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    hello_mode = loop.add_mode("hello")
    hello_mode.add_renderer(
        TextRendering.default(text="Hello, world!", y_location=16)
    )
```

Key concepts:

- `loop.add_mode(<name or renderer>)` registers a selectable mode in the UI. You
  can pass a string label or a renderer instance that provides its own title
  screen.
- `mode.add_renderer(...)` attaches one or more renderers that draw each frame
  for the mode. Renderers run sequentially, so you can stack overlays on top of
  base animations.
- `loop.app_controller.add_sleep_mode()` appends a low-power fallback that keeps
  the LED wall dim when no primary scenes are playing. The CLI toggles this
  behavior with the `--add-low-power-mode/--no-add-low-power-mode` flag.

## Building playlists

The `heart.navigation` module includes helpers for composing scenes:

- `MultiScene` rotates through renderers on a timer. Use this to build playlists
  that cycle automatically.
- `ComposedRenderer` stacks multiple renderers together. A common pattern is to
  place a text overlay on top of an animation.

Example snippet from `lib_2025.py`:

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

## Accessing peripherals

Peripherals publish data through modules under `heart.peripheral`. Renderers can
pull the latest readings directly:

```python
from heart.peripheral.heart_rates import current_bpms


class HeartRateVisualization(BaseRenderer):
    def render(self, surface: pygame.Surface, *_: Any) -> None:
        bpm = current_bpms().average
        # Draw something based on bpm
```

Peripheral managers start automatically when the loop boots. You do not need to
instantiate them manually inside configurations.

## Testing new configurations

1. Create your module under `heart/programs/configurations/`. Name it with a
   descriptive suffix (for example `festival_2025.py`).
1. Run the configuration locally:
   ```bash
   totem run --configuration festival_2025
   ```
1. Iterate until the playlist looks right. Use `--no-add-low-power-mode` if you
   want the scenes to loop continuously without the sleep fallback.

Check the console output for `Importing configuration: ...` lines to confirm that
your module loads successfully. When satisfied, commit the module alongside any
assets it requires (sprite sheets, sound files, etc.).

## Shipping configurations

- Store large assets in `src/heart/assets/` so they ship with the package.
- Document special hardware dependencies in `docs/devlog/` or in a dedicated
  README within the configuration folder.
- Consider adding unit or integration tests under `tests/` if the configuration
  includes complex business logic (for example, custom scheduling or state
  machines).

With these guidelines you can create repeatable playlists that take advantage of
Heart's renderer ecosystem and hardware integrations.
