# Heart Runtime

## Problem Statement

Provide an extensible runtime that drives an LED totem using pygame-based renderers, configuration playlists, and peripheral integrations.

## Materials

- Python 3.11 or newer with `uv` or another virtual environment manager.
- SDL-compatible graphics stack for local development (SDL2 libraries on Linux, built-ins on macOS).
- Optional Raspberry Pi with RGB LED matrix hardware for deployment.
- Access to Bluetooth controllers, switches, and sensors when exercising peripherals.

## Technical Approach

The runtime packages two Typer CLIs: `totem` orchestrates configuration loading, render loops, and firmware updates, while `totem_debug` surfaces hardware diagnostics. Renderers run inside a pygame game loop, peripheral workers feed data through the `PeripheralManager`, and display services target either a local window or the LED matrix.

## Quick Start
1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:
   ```bash
   make install
   ```
3. Launch the default playlist:
   ```bash
   uv run totem run --configuration lib_2025
   ```
4. Review [docs/getting_started.md](docs/getting_started.md) for Raspberry Pi deployment, hardware wiring, and CLI options.

## Command-Line Interfaces
| Command | Purpose |
| --- | --- |
| `totem` | Runs the runtime (`totem run`), updates firmware (`totem update-driver`), and manages renderer options. |
| `totem_debug` | Provides hardware diagnostics, including Bluetooth scanning, UART inspection, and accelerometer streaming. |

Key `totem run` flags:
- `--configuration <name>` selects modules from `heart.programs.configurations`.
- `--x11-forward` forces a pygame window even when the RGB matrix driver is active.
- `--add-low-power-mode/--no-add-low-power-mode` toggles the standby mode that keeps LEDs dim when no scenes are active.

## Architecture Summary
- `heart/environment.py` defines the `GameLoop` responsible for frame pacing and peripheral coordination.
- `heart.display.renderers` hosts animations, overlays, and HUDs that can be composed into playlists.
- `heart.device` contains output adapters such as `LocalScreen` and `LEDMatrix`.
- `heart.peripheral.core.manager.PeripheralManager` supervises switches, gamepads, heart-rate monitors, and other inputs.

See the following references for deeper analysis:
- [docs/runtime_overview.md](docs/runtime_overview.md) for loop orchestration details.
- [docs/code_flow.md](docs/code_flow.md) for a diagram of launch and render paths.
- [docs/program_configuration.md](docs/program_configuration.md) for playlist authoring guidance.

## Hardware Integration
- `LEDMatrix` streams frames to the RGB matrix when `HEART_USE_ISOLATED_RENDERER=1`.
- Bluetooth gamepads, switches, accelerometers, and heart-rate sensors publish data through the event bus managed by the peripheral subsystem.
- `totem update-driver --name <driver>` flashes device firmware located in `drivers/`.
- [docs/hardware_debug_cli.md](docs/hardware_debug_cli.md) documents debugging helpers for pairing controllers and inspecting UART traffic.

## Development Workflow
- `make install` sets up the editable package and dev extras using `uv`.
- `make format` applies Ruff, isort, Black, docformatter, and mdformat; run before committing.
- `make test` executes the pytest suite.
- `make check` verifies formatting and linting without applying fixes.

The repository layout is summarised below:
```
heart/
├── docs/                     # Architecture guides, dev logs, hardware notes
├── drivers/                  # Firmware flashing utilities
├── experimental/             # Prototypes (MQTT sidecar, broker helpers)
├── src/heart/                # Runtime, renderers, peripherals, utilities
├── tests/                    # Pytest suite
├── Makefile                  # Common developer tasks
└── pyproject.toml            # Packaging metadata and tool configuration
```

## Contributing
1. Fork the repository and create a topic branch.
2. Run `make format` and `make test` before pushing changes.
3. Update documentation when introducing new renderers, configurations, or hardware capabilities. Re-render diagrams with `scripts/render_code_flow.py` when architecture changes.

Please share findings, logs, or deployment results via issues or pull requests so the team can review them alongside the code changes.
