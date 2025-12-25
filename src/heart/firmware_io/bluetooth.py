from __future__ import annotations

from typing import Any

from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

logger = get_logger(__name__)

BLERadio: type[Any] | None = None
ProvideServicesAdvertisement: type[Any] | None = None
UARTService: type[Any] | None = None

ble_module = optional_import("adafruit_ble", logger=logger)
advertising_module = optional_import(
    "adafruit_ble.advertising.standard",
    logger=logger,
)
services_module = optional_import(
    "adafruit_ble.services.nordic",
    logger=logger,
)

if ble_module is not None and advertising_module is not None and services_module is not None:
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


# TODO: AAddDd a bulk write command
def send(messages: list[str]):
    _require_ble_dependencies()

    if not ble.advertising:
        if advertisement is None:
            raise ModuleNotFoundError(
                "ProvideServicesAdvertisement is unavailable. "
                "Install the adafruit_ble package to advertise over BLE."
            )
        ble.start_advertising(advertisement)

    if ble.connected:
        # We're connected, make sure the buffer is drained as the first priority
        for message in messages:
            uart.write(message.encode(ENCODING))
            uart.write(END_OF_MESSAGE_DELIMETER.encode(ENCODING))
