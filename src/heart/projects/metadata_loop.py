import os
import threading

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import logging
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.input.environment import GameLoop
import platform
from openant.easy.node import Node
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.heart_rate import HeartRate, HeartRateData


logger = logging.getLogger(__name__)


def detect_heart_rate(screens):
    node = Node()
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    device = HeartRate(node, device_id=0)

    def on_found():
        print(f"Device {device} found and receiving")

    def on_device_data(page: int, page_name: str, data):
        if isinstance(data, HeartRateData) and page == 128:
            print(f"Heart rate update {data.beat_count} beats from {page} {page_name}")
            screens[0].add_data(data)

    device.on_found = on_found
    device.on_device_data = on_device_data

    try:
        print(f"Starting {device}, press Ctrl-C to finish")
        node.start()
    except KeyboardInterrupt:
        print("Closing ANT+ device...")
    finally:
        device.close_channel()
        node.stop()


def run():
    devices = []
    if platform.system() == "Linux":
        from heart.projects.rgb_display import LEDMatrix

        devices.append(LEDMatrix())

    loop = GameLoop(64, 64, devices=devices)

    screens = [
        MetadataScreen(0, 0, "pink"),
        MetadataScreen(32, 0, "yellow"),
        MetadataScreen(0, 32, "blue"),
        MetadataScreen(32, 32, "green"),
    ]

    loop.add_renderer(screens[0])
    loop.add_renderer(screens[1])
    loop.add_renderer(screens[2])
    loop.add_renderer(screens[3])

    if platform.system() == "Linux":
        # Start heart detection in another thread
        def my_function():
            # Your code to run in the separate thread goes here
            detect_heart_rate(screens)

        # Create a new thread
        my_thread = threading.Thread(target=my_function)

        # Start the thread
        my_thread.start()

    loop.start()


if __name__ == "__main__":
    run()
