"""Command line interface bundling miscellaneous debug helpers."""

from __future__ import annotations

import typer

from . import debug

app = typer.Typer(help="Totem debugging helpers.")

gamepad_app = typer.Typer(help="Bluetooth gamepad utilities.")
app.add_typer(gamepad_app, name="gamepad")


@app.command(name="peripherals")
def list_peripherals() -> None:
    """List detected peripherals."""

    peripherals = debug.detect_peripherals()
    typer.echo(f"Detected {len(peripherals)} peripheral(s).")
    for peripheral in peripherals:
        typer.echo(f"- {peripheral}")


@app.command(name="accelerometer")
def stream_accelerometer(
    raw: bool = typer.Option(False, help="Echo raw serial data in addition to processed values."),
    sleep_interval: float = typer.Option(
        0.0,
        min=0.0,
        help="Sleep duration (seconds) between polling cycles."
    ),
) -> None:
    """Stream accelerometer readings."""

    debug.stream_accelerometer(raw=raw, sleep_interval=sleep_interval)


@app.command(name="uart")
def listen_uart() -> None:
    """Listen for raw UART events from the first discovered Bluetooth switch."""

    debug.listen_to_uart()


@app.command(name="bluetooth-switch")
def listen_bluetooth_switch() -> None:
    """Listen for events from all discovered Bluetooth switches."""

    debug.listen_to_bluetooth_switch()


@app.command(name="phone-text")
def run_phone_text() -> None:
    """Run the PhoneText BLE peripheral helper."""

    debug.run_phone_text()


@gamepad_app.command(name="scan")
def scan_gamepads(scan_duration: int = typer.Option(10, min=1, help="Scan duration in seconds.")) -> None:
    """Scan for Bluetooth controllers."""

    all_devices, matched_devices = debug.find_gamepad_devices(scan_duration=scan_duration)

    typer.echo("All Bluetooth devices found:")
    for device in all_devices:
        marker = "***" if device in matched_devices else " - "
        typer.echo(f"{marker} {device}")

    if matched_devices:
        typer.echo(f"\nFound {len(matched_devices)} potential 8BitDo devices.")
    else:
        typer.echo("\nNo 8BitDo controllers discovered. Ensure pairing mode is enabled.")


@gamepad_app.command(name="pair")
def pair_gamepad(mac_address: str = typer.Argument(..., help="MAC address of the controller to pair.")) -> None:
    """Attempt to pair and connect to a Bluetooth gamepad."""

    result = debug.pair_gamepad(mac_address)
    if "Connection successful" in result.stdout:
        typer.secho("Successfully connected to the controller!", fg=typer.colors.GREEN)
    else:
        typer.secho("Connection attempt completed. Check controller status.", fg=typer.colors.YELLOW)
        if result.stdout:
            typer.echo("bluetoothctl output:\n" + result.stdout.strip())
        if result.stderr:
            typer.echo("bluetoothctl errors:\n" + result.stderr.strip())


def main() -> None:
    """Entry-point used by ``pyproject.toml``."""

    app()


if __name__ == "__main__":
    main()
