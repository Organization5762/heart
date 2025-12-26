# Getting Started

## Problem Statement

Set up a repeatable Heart runtime environment so contributors can run `totem` locally, validate
hardware paths, and deploy to Raspberry Pi targets without reverse engineering the setup.

## Materials

- Python 3.11+ with `uv` (or another virtual environment manager).
- Heart repository checkout.
- SDL2 runtime libraries for local rendering (for example, `libsdl2-dev` and
  `libsdl2-image-dev` on Debian-based systems).
- For Raspberry Pi deployment: Raspberry Pi OS Bookworm or newer, SPI enabled, and wiring that
  matches the `rpi-rgb-led-matrix` documentation.

## Environment Setup

Create a virtual environment and install dependencies:

```bash
uv venv
source .venv/bin/activate
make install
```

`make install` installs the editable `heart` package with development extras. The equivalent
manual command is:

```bash
uv pip install -e .[dev]
```

## Local Runtime Execution

Run the default configuration:

```bash
totem run --configuration lib_2025
```

Useful flags:

- `--configuration <name>`: load a module from `heart.programs.configurations`.
- `--x11-forward`: force a pygame window even when LED matrix hardware is present.
- `--add-low-power-mode/--no-add-low-power-mode`: toggle idle power management.

## Display Layout Configuration

Set display geometry with environment variables instead of editing code:

- `HEART_DEVICE_LAYOUT`: `cube` (default) or `rectangle`.
- `HEART_LAYOUT_COLUMNS` / `HEART_LAYOUT_ROWS`: panel grid dimensions for rectangular layouts.
- `HEART_PANEL_COLUMNS` / `HEART_PANEL_ROWS`: per-panel pixel dimensions (default `64×64`).

Example for a 2×2 wall of 64×64 panels:

```bash
export HEART_DEVICE_LAYOUT=rectangle
export HEART_LAYOUT_COLUMNS=2
export HEART_LAYOUT_ROWS=2
export HEART_PANEL_COLUMNS=64
export HEART_PANEL_ROWS=64
```

## Raspberry Pi Deployment

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install -y git python3-dev python3-venv libsdl2-dev libsdl2-image-dev \
       libopenjp2-7 libtiff5 libatlas-base-dev libboost-all-dev
   ```
1. Clone and install the project:
   ```bash
   git clone https://github.com/<your-org>/heart.git
   cd heart
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .[dev]
   ```
1. Configure headless rendering for the RGB matrix:
   ```bash
   export SDL_VIDEODRIVER="dummy"
   export HEART_USE_ISOLATED_RENDERER=1
   ```
1. Start the runtime:
   ```bash
   totem run --configuration lib_2025
   ```

## Isolated Renderer I/O Tuning

When routing frames through the isolated renderer, adjust these environment variables to control
acknowledgement waits and deduplication:

- `HEART_ISOLATED_RENDERER_ACK_STRATEGY` (`always` or `never`).
- `HEART_ISOLATED_RENDERER_ACK_TIMEOUT_MS` (milliseconds).
- `HEART_ISOLATED_RENDERER_DEDUP_STRATEGY` (`none`, `source`, or `payload`).

## Hardware Validation

Use `totem_debug` to validate peripherals and transports before running the full runtime:

```bash
totem_debug peripherals
totem_debug accelerometer
totem_debug gamepad scan
```

See `docs/library/tooling_and_configuration.md` for the full command catalog.

## Driver Firmware Updates

Update driver firmware with the consolidated CLI:

```bash
totem update-driver --name <driver-name>
```

Each driver implements `heart.manage.update.main` to report success or failure through the
command output.

## Related References

- `docs/library/runtime_systems.md` for runtime topology and event flow.
- `docs/library/tooling_and_configuration.md` for configuration modules and CLI tooling.
- `docs/devlog/` for dated engineering notes.
