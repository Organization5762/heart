import os
import threading
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import logging
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.input.environment import GameLoop
import platform
from openant.easy.node import Node
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.heart_rate import HeartRate, HeartRateData
from bluepy.btle import Peripheral, DefaultDelegate, BTLEDisconnectError


logger = logging.getLogger(__name__)


class HRDelegate(DefaultDelegate):
    def __init__(self, screen):
        DefaultDelegate.__init__(self)
        self.screen = screen

    def handleNotification(self, cHandle, data):
        heart_rate = data[1]
        self.screen.heart_rate = heart_rate
        self.screen.heart_rate_data = None
        print(f"Heart Rate: {heart_rate} for {self.screen.color}")


def detect_ant_heart_rate(screens):
    node = Node()
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    device = HeartRate(node, device_id=0)

    def on_found():
        print(f"Device {device} found and receiving")

    def on_device_data(page: int, page_name: str, data):
        if isinstance(data, HeartRateData) and page == 128:
            print(f"Heart rate update {data.beat_count} beats from {page} {page_name}")
            screens[0].add_data(data)

    def on_channel_closed():
        print("Device channel has been closed. Device disconnected.")
        screens[0].heart_rate = 0

    device.on_found = on_found
    device.on_device_data = on_device_data
    device.on_channel_closed = on_channel_closed

    try:
        print(f"Starting {device}, press Ctrl-C to finish")
        node.start()
    except KeyboardInterrupt:
        print("Closing ANT+ device...")
    finally:
        device.close_channel()
        node.stop()


def detect_ble_heart_rate(screens):
    peripherals = [
        {
            "address": "cc:4d:5a:4b:8c:b6",
            "type": "random",
            "object": None,
            "screen_idx": 2,
        },
        {
            "address": "f0:13:c3:ed:f4:ea",
            "type": "public",
            "object": None,
            "screen_idx": 3,
        },
    ]

    try:
        while True:
            for peripheral in peripherals:
                if peripheral["object"] is None:
                    try:
                        peripheral["object"] = Peripheral(
                            peripheral["address"], peripheral["type"]
                        )
                        peripheral["object"].setDelegate(
                            HRDelegate(screens[peripheral["screen_idx"]])
                        )

                        hr_service = peripheral["object"].getServiceByUUID(
                            "0000180d-0000-1000-8000-00805f9b34fb"
                        )
                        hr_char = hr_service.getCharacteristics(
                            "00002a37-0000-1000-8000-00805f9b34fb"
                        )[0]

                        peripheral["object"].writeCharacteristic(
                            hr_char.valHandle + 1, b"\x01\x00"
                        )
                    except BTLEDisconnectError as e:
                        print(f"Failed to connect, retrying...")
                else:
                    try:
                        peripheral["object"].waitForNotifications(0.2)
                    except Exception as e:
                        print(e)

            time.sleep(0.5)
    finally:
        for peripheral in peripherals:
            if peripheral["object"] is not None:
                peripheral["object"].disconnect()


def run():
    devices = []
    if platform.system() == "Linux":
        from heart.projects.rgb_display import LEDMatrix

        devices.append(LEDMatrix())

    loop = GameLoop(64, 64, devices=devices)

    screens = [
        MetadataScreen(0, 0, "green"),
        MetadataScreen(32, 0, "yellow"),
        MetadataScreen(0, 32, "teal"),
        MetadataScreen(32, 32, "purple"),
        MetadataScreen(0, 0, "orange"),
        MetadataScreen(32, 0, "blue"),
        MetadataScreen(0, 32, "bluer"),
        MetadataScreen(32, 32, "pink"),
    ]

    loop.add_renderer(screens[0])
    loop.add_renderer(screens[1])
    loop.add_renderer(screens[2])
    loop.add_renderer(screens[3])

    if platform.system() == "Linux":
        # So far we can use BLE for everything, we can reactivate ANT if needed
        # def ant():
        #     detect_ant_heart_rate(screens)

        # my_thread = threading.Thread(target=ant)
        # my_thread.start()

        def ble():
            detect_ble_heart_rate(screens)

        my_thread = threading.Thread(target=ble)
        my_thread.start()

    loop.start()


if __name__ == "__main__":
    run()
