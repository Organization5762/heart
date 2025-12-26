# Tooling and Configuration

## Problem Statement

Consolidate CLI entrypoints, configuration module conventions, and tooling references so
operators and developers can locate the right command without scanning multiple short notes.

## Materials

- Python 3.11+ environment with the Heart runtime installed.
- `uv` for invoking repository tooling.
- Access to the Heart repository when editing configuration modules.

## CLI Entry Points

- `totem` is the primary runtime CLI (`src/heart/loop.py`).
- `totem_debug` is the hardware validation CLI (`src/heart/cli/debug_app.py`).
- Command implementations live under `src/heart/cli/`.

## Configuration Modules

Configuration modules live under `heart.programs.configurations` and expose
`configure(loop: GameLoop) -> None`.

Key patterns:

- Register modes with `loop.add_mode(...)`.
- Resolve renderers through `mode.resolve_renderer(loop.context_container, RendererClass)`.
- Compose renderers with `ComposedRenderer` or schedule them with `MultiScene`.
- Toggle a low-power fallback via `loop.app_controller.add_sleep_mode()`.

Minimal example:

```python
from heart.environment import GameLoop
from heart.renderers.text import TextRendering


def configure(loop: GameLoop) -> None:
    hello_mode = loop.add_mode("hello")
    hello_mode.add_renderer(TextRendering.default(text="Hello, world!", y_location=16))
```

## Hardware Debug CLI

Common `totem_debug` commands:

```bash
totem_debug peripherals
totem_debug accelerometer
totem_debug bluetooth-switch
totem_debug gamepad scan
```

Use `totem_debug --help` for the full command list.

## Logging Control

The shared log sampling controller is exposed through
`heart.utilities.logging_control.get_logging_controller()`.

- `HEART_LOG_DEFAULT_INTERVAL` sets the default sample cadence (`none` to disable sampling).
- `HEART_LOG_RULES` accepts comma-separated rules of the form
  `<key>=<interval>[:<LEVEL>[:<FALLBACK>]]`.

## Sync Harness

The sync harness under `scripts/sync_harness.py` supports build and deployment workflows. Run
`uv run python scripts/sync_harness.py --help` for supported operations.

## Static Analysis

- `make check` runs linting and formatting checks without applying fixes.
- `make format` applies Ruff, isort, Black, docformatter, and mdformat fixes.

## Publishing

Release scripts live in `scripts/publish_pypi.sh`. The standard flow is:

```bash
./scripts/publish_pypi.sh
```

## Related References

- `docs/books/getting_started.md` for environment setup.
- `docs/library/runtime_systems.md` for runtime details and event flow.
