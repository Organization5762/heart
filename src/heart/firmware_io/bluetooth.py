from __future__ import annotations

from typing import Any

from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import_attribute

logger = get_logger(__name__)

BLERadio: type[Any] | None = None
ProvideServicesAdvertisement: type[Any] | None = None
UARTService: type[Any] | None = None

BLERadio = optional_import_attribute("adafruit_ble", "BLERadio", logger=logger)
ProvideServicesAdvertisement = optional_import_attribute(
    "adafruit_ble.advertising.standard",
    "ProvideServicesAdvertisement",
    logger=logger,
)
UARTService = optional_import_attribute(
    "adafruit_ble.services.nordic",
    "UARTService",
    logger=logger,
)


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
