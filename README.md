# Heart

Visual display project for LED screens.

## Development

**Installation**

`make install`

**Formatting**

`make format` should install and run the correct formatting and linting tools

**Hardware debugging helpers**

Legacy scripts for inspecting peripherals have moved into a single Typer-based command line interface.
After installing the project in editable mode (for example via `pip install -e .[dev]`), run `totem_debug --help` to see the
available subcommands. A few useful entry points include:

- `totem_debug peripherals` – list devices detected by the peripheral manager.
- `totem_debug accelerometer` – stream accelerometer readings to the console.
- `totem_debug gamepad scan` – scan for nearby Bluetooth controllers.
- `totem_debug gamepad pair <mac>` – attempt to pair with a controller.

**Testing Locally**

The command: `totem run --configuration full_screen_test` should display a scene locally. If you see a scene, then the setup is correct.

**Supported Platforms**

- MacOSX for local development
- An appropriately setup Raspberry Pi 4 for portable use

## Drivers setup

### ANT

For ant you will need to run drivers/ant_dongle/setup.sh on the raspberry pi. Then unplug and replug the dongle
