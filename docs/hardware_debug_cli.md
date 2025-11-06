# Totem hardware debugging CLI

The legacy helpers from the `scripts/` directory have been folded into the
`totem_debug` Typer command so that tooling stays discoverable and consistent.
Install the project in editable mode first:

```bash
uv pip install -e .[dev]
```

Run `totem_debug --help` to see the full command tree. The most common entry
points are listed below.

## Peripheral inspection

```bash
totem_debug peripherals
```

Detects peripherals through `heart.peripheral.core.manager.PeripheralManager`
and prints the number of discovered devices along with their names.

## Accelerometer streaming

```bash
totem_debug accelerometer [--raw] [--sleep-interval <seconds>]
```

Streams accelerometer readings to the console using the same logic that backed
`scripts/test_accelerometer.py`. Use `--raw` to echo serial frames and
`--sleep-interval` to throttle polling.

## UART helpers

```bash
totem_debug uart
```

Starts a `BluetoothSwitch` UART listener and prints decoded JSON events. The
command runs until it is interrupted with <kbd>Ctrl</kbd>+<kbd>C</kbd>.

```bash
totem_debug bluetooth-switch
```

Subscribes to events from every detected switch and dumps each payload to the
console.

## PhoneText peripheral

```bash
totem_debug phone-text
```

Launches the `heart.peripheral.phone_text.PhoneText` helper. This mirrors the
old `scripts/test_phone_text.py` entry-point.

## Bluetooth gamepad utilities

```bash
totem_debug gamepad scan [--scan-duration <seconds>]
```

Scans for Bluetooth devices, highlighting potential 8BitDo controllers. The
output contains every device seen during the scan so it remains useful even if
no matches are found.

```bash
totem_debug gamepad status <mac>
```

Displays whether the selected controller is currently paired and/or connected.
This is the command to reach for before attempting to reconnect to a known
controller.

```bash
totem_debug gamepad pair <mac>
```

Pairs with a controller if necessary and then attempts to connect, printing the
result from `bluetoothctl`. The command also summarises the before/after
connection state so you can quickly tell if the operation succeeded.
