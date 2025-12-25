from __future__ import annotations

import importlib
import importlib.util
from typing import Any

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

BLERadio: type[Any] | None = None
ProvideServicesAdvertisement: type[Any] | None = None
UARTService: type[Any] | None = None

def _safe_find_spec(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        logger.debug("BLE dependency lookup failed for %s.", module_name)
        return False


if (
    _safe_find_spec("adafruit_ble")
    and _safe_find_spec("adafruit_ble.advertising.standard")
    and _safe_find_spec("adafruit_ble.services.nordic")
):
    try:
        ble_module = importlib.import_module("adafruit_ble")
        advertising_module = importlib.import_module("adafruit_ble.advertising.standard")
        services_module = importlib.import_module("adafruit_ble.services.nordic")
    except Exception:
        logger.debug("BLE dependencies failed to import. BLE support is disabled.")
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
