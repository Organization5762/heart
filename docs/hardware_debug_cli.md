# Totem Hardware Debugging CLI

## Problem Statement

Provide repeatable console commands for validating peripherals, UART devices, and Bluetooth controllers used by the Heart runtime.

## Materials

- Editable installation of the `heart` project (`uv pip install -e .[dev]`).
- Access to target peripherals (accelerometers, Bluetooth switches, controllers, phone text bridge).
- Terminal with permissions to access serial ports and Bluetooth adapters.

## Technical Approach

`totem_debug` is a Typer application that wraps the legacy scripts formerly stored in `scripts/`. Each subcommand exercises the same managers that power the runtime so test results align with production behaviour.

Run `totem_debug --help` to inspect the full command tree.

## Peripheral Inspection

```bash
totem_debug peripherals
```

Enumerates devices through `heart.peripheral.core.manager.PeripheralManager` and prints discovered types and counts.

## Accelerometer Streaming

```bash
totem_debug accelerometer [--raw] [--sleep-interval <seconds>]
```

Reads serial frames from accelerometer peripherals. `--raw` echoes the unparsed payload, and `--sleep-interval` throttles polling.

## UART Helpers

```bash
totem_debug uart
```

Starts a `BluetoothSwitch` UART listener and dumps decoded JSON events until interrupted with <kbd>Ctrl</kbd>+<kbd>C</kbd>.

```bash
totem_debug bluetooth-switch
```

Subscribes to every detected switch and prints the event payload stream.

## PhoneText Peripheral

```bash
totem_debug phone-text
```

Launches the `heart.peripheral.phone_text.PhoneText` helper to validate the SMS relay used in installations.

## Bluetooth Gamepad Utilities

```bash
totem_debug gamepad scan [--scan-duration <seconds>]
```

Scans for Bluetooth devices and highlights potential 8BitDo controllers while still listing all observed devices.

```bash
totem_debug gamepad status <mac>
```

Reports whether the specified controller is paired and connected.

```bash
totem_debug gamepad pair <mac>
```

Pairs and connects to a controller, printing the before/after state from `bluetoothctl` so you can confirm success.
