# Getting Started

## Problem Statement

Set up a repeatable development environment for the Heart runtime so contributors can run `totem` locally, deploy to Raspberry Pi hardware, and exercise peripheral debugging workflows without guesswork.

## Materials

- Python 3.11 or newer with [`uv`](https://docs.astral.sh/uv/) or another virtual environment manager.
- SDL2 runtime libraries on the workstation (Mesa packages on Linux, system defaults on macOS).
- For Raspberry Pi deployments: Raspberry Pi OS Bookworm or newer with SPI enabled and wiring that matches the [`rpi-rgb-led-matrix`](https://github.com/hzeller/rpi-rgb-led-matrix) documentation.
- Access to the `heart` repository and network connectivity for dependency installation.

## Technical Approach

1. Create an isolated Python environment and install the project with development extras.
1. Use the `totem` Typer CLI to exercise the runtime locally through a pygame window or remotely on a Pi-backed LED matrix.
1. Configure peripherals with the `totem_debug` helpers to validate hardware paths before the main loop runs.

## Environment Setup

Clone the repository, create a virtual environment, and upgrade `pip`:

```bash
uv venv
source .venv/bin/activate
uv pip install --upgrade pip
```

Install project dependencies and tooling:

```bash
make install
```

The `make` target installs the editable `heart` package and its `dev` extras. The equivalent manual command is:

```bash
uv pip install -e .[dev]
```

## Local Runtime Execution

Launch the runtime with the default configuration:

```bash
totem run --configuration lib_2025
```

Important flags:

- `--configuration <name>`: load a module from `heart.programs.configurations`.
- `--x11-forward`: force a pygame window, even on systems with the LED matrix attached.
- `--add-low-power-mode/--no-add-low-power-mode`: control the idle power management loop.
- `--layout-columns` and `--layout-rows`: override the display layout when running non-cube panel configurations.

Ensure SDL dependencies are installed (`libsdl2-dev` and `libsdl2-image-dev` on Debian-based systems) if the window fails to open.

## Raspberry Pi Deployment Procedure

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install -y git python3-dev python3-venv libsdl2-dev libsdl2-image-dev \
       libopenjp2-7 libtiff5 libatlas-base-dev libboost-all-dev
   ```
1. Clone the repository and install in editable mode:
   ```bash
   git clone https://github.com/<your-org>/heart.git
   cd heart
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .[dev]
   ```
1. Configure rendering for the RGB matrix:
   ```bash
   export SDL_VIDEODRIVER="dummy"
   export HEART_USE_ISOLATED_RENDERER=1
   ```
   The dummy SDL driver allows pygame to run headless; the environment variable routes frames to the isolated RGBMatrix renderer.
1. Start the runtime:
   ```bash
   totem run --configuration lib_2025
   ```

Set `--x11-forward` if you require a remote preview window while connected over SSH with X forwarding.

## Peripheral Configuration

`heart.peripheral.core.manager.PeripheralManager` supervises worker threads. Supported devices include:

- Bluetooth switches for scene control. Pair and test them with `totem_debug gamepad` (see [hardware_debug_cli.md](hardware_debug_cli.md)).
- ANT+/BLE heart-rate monitors handled by `heart.peripheral.heart_rates`.
- Serial accelerometers and mixed sensor boards validated with `totem_debug accelerometer`.

Inactive devices emit warnings but do not halt the runtime.

Use environment variables to target specific hardware when multiple devices are paired:

- `HEART_BLE_DEVICE_NAME` selects the BLE peripheral name used for UART listeners.
- `HEART_GAMEPAD_MAC` sets a Bluetooth MAC address to auto-connect via `bluetoothctl`.
- `HEART_LAYOUT_COLUMNS` and `HEART_LAYOUT_ROWS` set the default layout when CLI flags are not provided.

## Debugging Interfaces

Use `totem_debug` for hardware validation. The subcommands cover Bluetooth discovery, UART tailing, sensor frame capture, and matrix diagnostics. Detailed usage lives in [hardware_debug_cli.md](hardware_debug_cli.md).

## Driver Firmware Updates

Drivers under `drivers/` expose update hooks through the consolidated CLI:

```bash
totem update-driver --name <driver-name>
```

Each driver implements `heart.manage.update.main` and reports success or failure directly through the command output.

## Additional References

- [Runtime overview](runtime_overview.md) documents loop orchestration and threading boundaries.
- [Program configuration](program_configuration.md) explains how scene playlists are assembled.
- `docs/devlog/` contains dated engineering logs for hardware bring-up and loop refinements.
