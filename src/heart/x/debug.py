"""Helper utilities backing the :mod:`heart.x` debug CLI."""

from __future__ import annotations

import json
import subprocess
import time
from typing import Sequence

from serial.serialutil import SerialException
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BluetoothSwitch


def detect_peripherals() -> Sequence[object]:
    """Detect connected peripherals using :class:`PeripheralManager`."""

    manager = PeripheralManager()
    manager.detect()
    return tuple(manager.peripheral)


def stream_accelerometer(raw: bool = False, sleep_interval: float = 0.0) -> None:
    """Stream accelerometer data to the console.

    The implementation mirrors the legacy ``test_accelerometer`` script and will
    keep running until interrupted via :class:`KeyboardInterrupt`.
    """

    manager = PeripheralManager()
    manager.detect()

    accelerometers = [
        peripheral for peripheral in manager.peripheral if isinstance(peripheral, Accelerometer)
    ]
    if not accelerometers:
        raise RuntimeError("No accelerometer peripherals detected")

    accelerometer = accelerometers[0]
    serial_connection = accelerometer._connect_to_ser()

    print("Starting accelerometer stream (press Ctrl+C to exit)...")

    try:
        while True:
            try:
                payload = serial_connection.readlines(serial_connection.in_waiting or 1)
            except SerialException:
                if sleep_interval:
                    time.sleep(sleep_interval)
                continue

            for packet in payload:
                accelerometer._process_data(packet)
                if raw:
                    try:
                        decoded = packet.decode("utf-8").rstrip()
                    except Exception:  # pragma: no cover - defensive decoding
                        decoded = str(packet)
                    print(decoded)

            print(accelerometer.acceleration_value)
            if sleep_interval:
                time.sleep(sleep_interval)
    except KeyboardInterrupt:
        print("Stopping accelerometer stream")
    finally:
        try:
            serial_connection.close()
        except Exception:
            pass


def listen_to_uart() -> None:
    """Listen for raw UART events using :class:`UartListener`."""

    devices = list(BluetoothSwitch.detect())
    if not devices:
        raise RuntimeError("No Bluetooth switches discovered")

    listener = devices[0].listener
    print("Starting UART listener...")
    listener.start()
    print("Listener started. Press Ctrl+C to stop.")

    try:
        while True:
            for event in listener.consume_events():
                print(json.dumps(event, indent=2, sort_keys=True))
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping listener")
    except RuntimeError as exc:
        print(f"Listener error: {exc}")
    finally:
        listener.close()


def listen_to_bluetooth_switch() -> None:
    """Listen for events from :class:`BluetoothSwitch` peripherals."""

    switches = list(BluetoothSwitch.detect())
    if not switches:
        raise RuntimeError("No Bluetooth switches discovered")

    for switch in switches:
        print(f"Starting listener for {switch}")
        switch.listener.start()

    try:
        while True:
            for switch in switches:
                for event in switch.listener.consume_events():
                    print(json.dumps(event, indent=2, sort_keys=True))
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping Bluetooth switch listeners")
    except RuntimeError as exc:
        print(f"Listener error: {exc}")
    finally:
        for switch in switches:
            switch.listener.close()


def run_phone_text() -> None:
    """Run the :class:`~heart.peripheral.phone_text.PhoneText` helper."""

    PhoneText().run()


def find_gamepad_devices(scan_duration: int = 10) -> tuple[list[str], list[str]]:
    """Scan for Bluetooth gamepads using ``bluetoothctl``.

    Returns a tuple ``(all_devices, matched_devices)`` mirroring the legacy
    ``test_gamepad_connect`` helper.
    """

    scan_proc = subprocess.Popen(
        ["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    try:
        time.sleep(max(scan_duration, 1))
        result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
    finally:
        scan_proc.terminate()

    all_devices = []
    matched_devices = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        all_devices.append(line)
        if "8BitDo" in line or "Pro Controller" in line:
            matched_devices.append(line)

    return all_devices, matched_devices


def pair_gamepad(mac_address: str) -> subprocess.CompletedProcess[str]:
    """Pair and connect to a Bluetooth gamepad."""

    subprocess.run(["bluetoothctl", "pair", mac_address], check=False)
    subprocess.run(["bluetoothctl", "trust", mac_address], check=False)
    return subprocess.run(["bluetoothctl", "connect", mac_address], capture_output=True, text=True)
