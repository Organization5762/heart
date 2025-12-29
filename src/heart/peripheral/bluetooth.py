import asyncio
import atexit
import functools
import json
import logging
import threading
import time
from collections import deque
from typing import Any, Iterator, NoReturn, cast

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from heart.peripheral.uart_buffer import UartMessageBuffer
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

# https://docs.nordicsemi.com/bundle/ncs-latest/page/nrf/libraries/bluetooth/services/nus.html#service_uuid
NOTIFICATION_CHANNEL = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SINGLE_CLIENT_TIMEOUT_SECONDS = 60 * 60 * 12  # 12 hours
OBJECT_SEPARATOR = b"\n"
RECONNECT_DELAY_SECONDS = 1.0
DEVICE_NAME = "totem-controller"


class UartListener:
    """Listeners for data come in as raw bytes from a UART Service."""

    __slots__ = (
        "device",
        "events",
        "disconnected",
        "_buffer",
        "_logger",
        "_log_controller",
        "_bytes_received",
        "_messages_received",
    )

    def __init__(self, device: BLEDevice) -> None:
        self.device = device
        self.events: deque[dict[str, Any]] = deque([], maxlen=50)
        self.disconnected = False
        self._buffer = UartMessageBuffer(
            strategy_provider=Configuration.ble_uart_buffer_strategy,
            delimiter=OBJECT_SEPARATOR,
        )
        self._logger = get_logger(f"{__name__}.{type(self).__name__}")
        self._log_controller = get_logging_controller()
        self._bytes_received = 0
        self._messages_received = 0

    @classmethod
    async def _discover_devices(cls) -> list[BLEDevice]:
        devices: list[BLEDevice] = await BleakScanner.discover()
        return [
            device
            for device in devices
            # TODO: This should come from somewhere more principled
            if device.name == DEVICE_NAME
        ]

    def start(self) -> None:
        self._logger.debug("Starting UART listener thread for %s", self.device.address)

        def _run_listener() -> None:
            try:
                asyncio.run(self.connect_and_listen())
            except Exception:
                self.disconnected = True
                self._logger.exception("UART listener thread terminated unexpectedly.")

        t = threading.Thread(
            target=_run_listener,
            name=f"UartListener-{self.device.address}",
        )
        atexit.register(t.join, timeout=1)
        t.start()

    def close(self) -> None:
        self._logger.debug("Closing UART listener for %s", self.device.address)
        self.disconnected = True

    def consume_events(self) -> Iterator[dict[str, Any]]:
        while self.events:
            if self.disconnected:
                raise RuntimeError("Device disconnected")
            yield self.events.popleft()

    async def connect_and_listen(self) -> NoReturn:
        self._logger.info("Found a device, starting listener loop")
        await self.__start_listener_loop(self.device)

    async def __start_listener_loop(self, device: BLEDevice) -> NoReturn:
        while True:
            # We still tend to loe a decent amount of data (~5 seconds worth)
            # as part of the reconnection process, but if the timeout is infrequent enough it would be hard to notice
            self._logger.info(
                "Attempting to connect to %s (%s).", device.address, device.name
            )

            # For now we just restart the listener, as whatever we lost in the reconnection
            # is likely going to be discarded as misaligned anyway
            self.__clear_buffer()

            # TODO: There is an issue where when you have the device in dev mode, the _device_
            # changes when new code gets flashed onto it.  I don't think this will happen in practice, but it:
            # 1. Makes developing kinda annoying
            # 2. Is a weird failure case where the Totem / main controller would need to be restarted
            async with self.__get_client(device) as client:
                # Try to connect if not connected
                if not client.is_connected:
                    await client.connect()

                # Otherwise use the notify channel
                await client.start_notify(
                    NOTIFICATION_CHANNEL, callback=self.__callback
                )
                await asyncio.sleep(SINGLE_CLIENT_TIMEOUT_SECONDS)
            # On failure, wait a bit before retrying
            time.sleep(RECONNECT_DELAY_SECONDS)

    @functools.cache
    def __get_client(self, device: BLEDevice) -> BleakClient:
        def on_disconnect(client: BleakClient) -> None:
            self.disconnected = True

        client = BleakClient(
            device,
            disconnected_callback=on_disconnect,
        )
        # https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/main/adafruit_ble/services/nordic.py#L47
        backend = cast(Any, client._backend)
        if hasattr(backend, "_mtu_size"):
            backend._mtu_size = 512
        return client

    def __callback(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """Callback function to handle incoming data from the UART service.

        Args:
            sender (BleakGATTCharacteristic): The characteristic that sent the data.
            data (bytearray): The data received from the characteristic.

        """
        self._bytes_received += len(data)
        for line in self._buffer.append(data):
            if not line:
                continue
            try:
                self.events.append(json.loads(line))
                self._messages_received += 1
            except json.decoder.JSONDecodeError:
                if isinstance(line, (bytes, bytearray)):
                    display_line = line.decode("utf-8", errors="ignore")
                else:
                    display_line = line
                self._logger.debug(
                    "Failed to decode payload: %s", display_line, exc_info=True
                )

        self._log_controller.log(
            key="ble.uart.poll",
            logger=self._logger,
            level=logging.INFO,
            msg="BLE UART stream stats bytes=%s messages=%s buffer=%s",
            args=(
                self._bytes_received,
                self._messages_received,
                self._buffer.buffer_size,
            ),
        )

    def __clear_buffer(self) -> None:
        self._buffer.clear()
