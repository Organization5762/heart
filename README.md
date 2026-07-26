# Heart Runtime

## Optional native RGB matrix runtime

Heart installs without native display support by default. The Raspberry Pi
HUB75 runtime lives in
[`Organization5762/heart-rgb-matrix-driver`](https://github.com/Organization5762/heart-rgb-matrix-driver)
and is pinned to an exact commit through the `native` extra.

Use `make install` for the default development environment. Use
`make bootstrap-native` when the native runtime is needed, or `make pi_install`
to configure and install a Raspberry Pi deployment. Direct source and wheel
installs use the same split:

```console
python -m pip install .
python -m pip install '.[native]'
make build
python -m pip install --find-links dist dist/heart-0.2.0-py3-none-any.whl
python -m pip install --find-links dist 'dist/heart-0.2.0-py3-none-any.whl[native]'
```

The wheel install uses the companion `heart-device-manager` and
`heart-firmware-io` wheels emitted by `make build`. Building the native extra
requires Rust. Default source and wheel installs do not.

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
   make run
   ```
4. Launch the default playlist with the Beats UI attached:
   ```bash
   uv run totem run --configuration lib_2025 --with-beats
   ```
5. Launch a different playlist:
   ```bash
   make run RUN_CONFIGURATION=your_configuration
   ```
6. Launch the Beats UI locally against a runtime already running on a Raspberry Pi:

   ```bash
   # On the Pi
   make run

   # On your laptop
   uv run totem run --with-beats --remote-runtime --beats-runtime-host totem.local
   ```

## Command-Line Interfaces

| Command       | Purpose                                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------------------------- |
| `totem`       | Runs the runtime (`totem run`), updates firmware (`totem update-driver`), and manages renderer options.    |
| `totem_debug` | Provides hardware diagnostics, including Bluetooth scanning, UART inspection, and accelerometer streaming. |

Key `totem run` flags:

- `--configuration <name>` selects modules from `heart.programs.configurations`.
- `--add-low-power-mode/--no-add-low-power-mode` toggles the standby mode that keeps LEDs dim when no scenes are active.
- `totem run --with-beats --configuration <name>` launches the totem runtime, a Beats control websocket for phone text/image/navigation commands, and a LAN-visible Beats web UI together, wiring `BEATS_WEBSOCKET_ENABLED=1`, `BEATS_WEBSOCKET_BIND_HOST=0.0.0.0`, and a Vite dev server on `http://localhost:5173`.
- `BEATS_WEB_ENABLED=1 totem run --configuration <name>` enables the same Beats web UI and phone-control websocket from an environment file or shell without setting `FORWARD_TO_BEATS_APP`.
- `totem run --with-beats --remote-runtime --beats-runtime-host totem.local` launches only the browser-served Beats UI and points it at an existing runtime websocket on the Pi.

## Architecture Summary

- `heart/environment.py` defines the `GameLoop` responsible for frame pacing and peripheral coordination.
- `heart.renderers` hosts animations, overlays, and HUDs that can be composed into playlists.
- `heart.device` contains output adapters such as `LocalScreen` and `LEDMatrix`.
- `heart.peripheral.core.manager.PeripheralManager` supervises switches, gamepads, heart-rate monitors, and other inputs.

See the following references for deeper analysis:

- [docs/library/runtime_systems.md](docs/library/runtime_systems.md) for loop orchestration details.
- [docs/code_flow.md](docs/code_flow.md) for a diagram of launch and render paths.
- [docs/library/tooling_and_configuration.md](docs/library/tooling_and_configuration.md) for playlist authoring guidance.
- [docs/books/development_workflow.md](docs/books/development_workflow.md) for the devex snapshot workflow.

## Hardware Integration

- `LEDMatrix` streams frames to the RGB matrix when `HEART_USE_ISOLATED_RENDERER=1`.
- Bluetooth gamepads, switches, accelerometers, and heart-rate sensors publish data through the event bus managed by the peripheral subsystem.
- `totem update-driver --name <driver>` flashes device firmware located in `drivers/`.
- [docs/library/tooling_and_configuration.md](docs/library/tooling_and_configuration.md) documents debugging helpers for pairing controllers and inspecting UART traffic.

## Development Workflow

- `make install` sets up the editable package and dev extras using `uv`.
- `make run` starts `uv run totem run --configuration lib_2025` with Beats streaming enabled on `0.0.0.0:8765`; override with `RUN_CONFIGURATION=<name>`.
- `make format` applies Ruff, isort, Black, docformatter, and mdformat; run before committing.
- `make test` executes the pytest suite.
- `make check` verifies formatting and linting without applying fixes.
- `make doctor` captures a developer experience snapshot for troubleshooting.
- Keep collection and element variable names distinct (for example, `sensors` and `sensor`).

The repository layout is summarised below:

```
heart/
├── docs/                     # Architecture guides, dev logs, hardware notes
├── drivers/                  # Firmware flashing utilities
├── experimental/             # Prototypes (MQTT sidecar, broker helpers)
├── packages/                 # Separately published helper packages
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
