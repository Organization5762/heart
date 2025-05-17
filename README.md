# Heart

Visual display project for LED screens.

## Development

**Installation**

`make install`

**Formatting**

`make format` should install and run the correct formatting and linting tools

**Testing Locally**

The command: `totem run --configuration full_screen_test` should display a scene locally. If you see a scene, then the setup is correct.

**Supported Platforms**

- MacOSX for local development
- An appropriately setup Raspberry Pi 4 for portable use

## Drivers setup

### ANT

For ant you will need to run drivers/ant_dongle/setup.sh on the raspberry pi. Then unplug and replug the dongle
