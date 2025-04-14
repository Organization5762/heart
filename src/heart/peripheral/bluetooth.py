import asyncio
from collections import deque
import functools
import json
import threading
from typing import Any, AsyncGenerator, AsyncIterator, Iterator, NoReturn
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak import BleakScanner

# https://docs.nordicsemi.com/bundle/ncs-latest/page/nrf/libraries/bluetooth/services/nus.html#service_uuid
NOTIFICATION_CHANNEL = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SINGLE_CLIENT_TIMEOUT_SECONDS = 60 * 60 * 12 # 12 hours
OBJECT_SEPARATOR = "\n"

class UartListener:
    """
    Listeners for data come in as raw bytes from a UART Service.  
    """
    __slots__ = ("device", "buffer", "events")

    def __init__(self, device: BLEDevice) -> None:
        self.device = device
        self.buffer: str = ""
        self.events: deque[dict[str, Any]] = deque([], maxlen=50)

    @classmethod
    def _discover_devices(cls) -> Iterator[BLEDevice]:
        devices: list[BLEDevice] = asyncio.run(BleakScanner.discover())
        for device in devices:
            # TODO: This should come from somewhere more principled
            if device.name == "totem-controller":
                yield device

    def start(self) -> None:
        t = threading.Thread(target=lambda: asyncio.run(self.connect_and_listen()))
        t.start()

    def close(self) -> None:
        pass

    def consume_events(self) -> Iterator[dict[str, Any]]:
        while self.events:
            yield self.events.popleft()

    async def connect_and_listen(self) -> NoReturn:
        print("Found a device, starting listener loop")
        await self.__start_listener_loop(self.device)

    async def __start_listener_loop(self, device: BLEDevice) -> NoReturn:
        while True:
            # We still tend to loe a decent amount of data (~5 seconds worth)
            # as part of the reconnection process, but if the timeout is infrequent enough it would be hard to notice
            print(f"Attempting to connect to {device.address} ({device.name}).")

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
                    NOTIFICATION_CHANNEL,
                    callback=self.__callback
                )
                
                await asyncio.sleep(SINGLE_CLIENT_TIMEOUT_SECONDS)

    @functools.cache
    def __get_client(self, device: BLEDevice) -> BleakClient:
        client = BleakClient(
            device,
            disconnected_callback=None,
        )
        # https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/main/adafruit_ble/services/nordic.py#L47
        client._backend._mtu_size = 512
        return client

    def __callback(self, sender: BleakGATTCharacteristic, data: bytearray):
        """
        Callback function to handle incoming data from the UART service.

        Args:
            sender (BleakGATTCharacteristic): The characteristic that sent the data.
            data (bytearray): The data received from the characteristic.
        """
        # Append the decoded data to the buffer
        self.buffer += self.__decode_read_data(data)

        if OBJECT_SEPARATOR in self.buffer:
            line, self.buffer = self.buffer.split(OBJECT_SEPARATOR, 1)

            try:
                self.events.append(json.loads(line))
            except json.decoder.JSONDecodeError as e:
                pass

    def __decode_read_data(self, data: bytearray) -> str:
        return data.decode("utf-8", errors="ignore")
    
    def __clear_buffer(self) -> None:
        self.buffer = ""