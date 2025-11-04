# Getting started

This guide walks through the essentials for running the Heart totem locally and
on production hardware. It assumes the v0.2+ release line where the runtime,
configuration registry, and debugging tooling have been consolidated around the
`totem` and `totem_debug` Typer applications.

## Prerequisites

- Python 3.11 or newer. We ship tooling through [`uv`](https://docs.astral.sh/uv/)
  to keep environments reproducible, but any virtual environment manager works.
- SDL-compatible GPU drivers. On macOS the system libraries are sufficient; on
  Linux you may need Mesa packages installed for pygame to create a window.
- For Raspberry Pi deployments: Raspberry Pi OS (Bookworm or newer) with SPI
  enabled and the RGB Matrix hat wired according to the
  [`rpi-rgb-led-matrix`](https://github.com/hzeller/rpi-rgb-led-matrix)
  documentation.

Clone the repository and create a virtual environment before moving forward.

```bash
uv venv
source .venv/bin/activate
uv pip install --upgrade pip
```

## Installing dependencies

All development dependencies, including linting and documentation tooling, can
be installed via the make helpers in the project root.

```bash
make install
```

This resolves the base `heart` package alongside the `dev` dependency group. If
you prefer manual control, the equivalent `uv` invocation is:

```bash
uv pip install -e .[dev]
```

## Running the totem locally

The Heart runtime ships as the `totem` console script. Running the totem locally
renders to a pygame window so you can iterate on scenes and peripheral logic
without hardware.

```bash
totem run --configuration lib_2025
```

Key flags:

- `--configuration <name>` selects a configuration module from
  `heart.programs.configurations`. The default `lib_2025` set is a curated mix of
  interactive and ambient scenes used at live installations.
- `--x11-forward` forces a pygame window even on a Raspberry Pi with the RGB
  matrix attached. This is invaluable for remote debugging through X forwarding.
- `--add-low-power-mode/--no-add-low-power-mode` toggles the fallback sleep mode
  that keeps the LED wall idle when no scenes are active.

On macOS you can run the command directly. On Linux desktops make sure the SDL
windowing dependencies are present (Ubuntu/Debian packages `libsdl2-dev` and
`libsdl2-image-dev`).

## Deploying to a Raspberry Pi

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install -y git python3-dev python3-venv libsdl2-dev libsdl2-image-dev \
       libopenjp2-7 libtiff5 libatlas-base-dev libboost-all-dev
   ```
2. Clone the project and install it in editable mode:
   ```bash
   git clone https://github.com/<your-org>/heart.git
   cd heart
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .[dev]
   ```
3. Configure the environment for the RGB matrix by exporting:
   ```bash
   export SDL_VIDEODRIVER="dummy"
   export HEART_USE_ISOLATED_RENDERER=1
   ```
   The first variable allows pygame to create surfaces without an attached HDMI
   display; the second routes rendering to the isolated RGBMatrix driver.
4. Launch the runtime:
   ```bash
   totem run --configuration lib_2025
   ```

The configuration loader automatically instantiates the LED matrix renderer when
`HEART_USE_ISOLATED_RENDERER` is present. If you connect through SSH with X11
forwarding and still want a preview window, run with `--x11-forward`.

## Peripheral setup

Peripheral workers are managed by
`heart.peripheral.core.manager.PeripheralManager`. The following devices are
supported out of the box:

- **Bluetooth switches** for triggering scene changes. Pair controllers with
  the `totem_debug gamepad` helpers documented in
  [`docs/hardware_debug_cli.md`](hardware_debug_cli.md).
- **Heart-rate monitors** (ANT+ or BLE) feeding into
  `heart.peripheral.heart_rates`. Connect receivers before starting the loop so
  the worker discovers them during startup.
- **Accelerometers and sensor boards** wired over serial. Use
  `totem_debug accelerometer` to validate wiring before letting the runtime read
  from them.

All peripheral threads start when `totem run` boots the `GameLoop`. Sensors that
are not connected will log warnings but will not crash the runtime.

## Debugging tools

The `totem_debug` command groups all hardware debugging scripts. Refer to the
[dedicated guide](hardware_debug_cli.md) for details on each helper. Typical
workflows include scanning for Bluetooth gamepads, tailing UART frames, and
streaming accelerometer data.

## Updating device firmware

Device firmware drivers live under `drivers/`. Use the consolidated `totem`
entry point to flash them:

```bash
totem update-driver --name <driver-name>
```

Driver modules implement `heart.manage.update.main` and are resolved from the
`drivers/` directory. The command reports success or failure directly in the
terminal output.

## Where to go next

- Read the [runtime overview](runtime_overview.md) to understand the main loop
  architecture.
- Explore [program configurations](program_configuration.md) to build your own
  playlists of renderers and scenes.
- Keep an eye on the `docs/devlog/` folder for historical notes about hardware
  bring-up and operations.
