from __future__ import annotations

import importlib
from typing import Any

BLERadio: type[Any] | None = None
ProvideServicesAdvertisement: type[Any] | None = None
UARTService: type[Any] | None = None

try:
    ble_module = importlib.import_module("adafruit_ble")
    advertising_module = importlib.import_module("adafruit_ble.advertising.standard")
    services_module = importlib.import_module("adafruit_ble.services.nordic")
except ImportError:
    pass
else:
    BLERadio = getattr(ble_module, "BLERadio", None)
    ProvideServicesAdvertisement = getattr(advertising_module, "ProvideServicesAdvertisement", None)
    UARTService = getattr(services_module, "UARTService", None)


if BLERadio is not None and UARTService is not None and ProvideServicesAdvertisement is not None:
    ble = BLERadio()
    uart = UARTService()
    advertisement = ProvideServicesAdvertisement(uart)
else:
    ble = None
    uart = None
    advertisement = None


def _require_ble_dependencies() -> None:
    if ble is None or uart is None:
        raise ModuleNotFoundError(
            "adafruit_ble is required to use heart.firmware_io.bluetooth. "
            "Install the CircuitPython BLE libraries to enable Bluetooth communication."
        )

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"


def send_bulk(messages: list[str]) -> None:
    _require_ble_dependencies()

    if not messages:
        return

    if not ble.advertising:
        if advertisement is None:
            raise ModuleNotFoundError(
                "ProvideServicesAdvertisement is unavailable. "
                "Install the adafruit_ble package to advertise over BLE."
            )
        ble.start_advertising(advertisement)

    if ble.connected:
        payload = END_OF_MESSAGE_DELIMETER.join(messages) + END_OF_MESSAGE_DELIMETER
        uart.write(payload.encode(ENCODING))


def send(messages: list[str]) -> None:
    send_bulk(messages)
