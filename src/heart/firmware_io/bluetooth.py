from __future__ import annotations

import importlib.util

if importlib.util.find_spec("adafruit_ble") is not None:
    from adafruit_ble import BLERadio
    from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
    from adafruit_ble.services.nordic import UARTService
else:  # pragma: no cover - exercised in environments without BLE dependencies
    class BLERadio:  # type: ignore[override]
        advertising = False
        connected = False

        def start_advertising(self, *_args, **_kwargs) -> None:  # noqa: D401 - simple stub
            """Signal that BLE support is unavailable."""

            msg = "adafruit_ble is required for Bluetooth LE support"
            raise ModuleNotFoundError(msg)

    class UARTService:  # type: ignore[override]
        def write(self, *_args, **_kwargs) -> None:  # noqa: D401 - simple stub
            """Signal that BLE support is unavailable."""

            msg = "adafruit_ble is required for Bluetooth LE support"
            raise ModuleNotFoundError(msg)

    class ProvideServicesAdvertisement:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs) -> None:  # noqa: D401 - simple stub
            """Signal that BLE support is unavailable."""

            msg = "adafruit_ble is required for Bluetooth LE support"
            raise ModuleNotFoundError(msg)

try:
    ble = BLERadio()
    uart = UARTService()
    advertisement = ProvideServicesAdvertisement(uart)
except ModuleNotFoundError:
    # ``tests/firmware_io/test_bluetooth.py`` monkeypatches these objects, so we
    # can safely provide inert placeholders when the dependency is missing.
    ble = BLERadio()
    uart = UARTService()
    advertisement = object()

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"


# TODO: AAddDd a bulk write command
def send(messages: list[str]):
    if not ble.advertising:
        ble.start_advertising(advertisement)

    if ble.connected:
        # We're connected, make sure the buffer is drained as the first priority
        for message in messages:
            uart.write(message.encode(ENCODING))
            uart.write(END_OF_MESSAGE_DELIMETER.encode(ENCODING))
