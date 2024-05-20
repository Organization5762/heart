import os
from heart.display.renderers.kirby import KirbyFlying

from heart.input.heart_rate import HeartRateSubscriber
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import threading
from heart.display.renderers.kirby_loop import KirbyLoop
from heart.input.env import Environment

from heart.input.switch import SwitchSubscriber

import logging
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.input.environment import GameLoop

logger = logging.getLogger(__name__)

def run():
    devices = []
    if Environment.is_pi():
        from heart.projects.rgb_display import LEDMatrix
        devices.append(LEDMatrix())

    loop = GameLoop(64, 64, devices=devices)

    screens = [
        MetadataScreen(0, 0, "pink"),
        MetadataScreen(32, 0, "yellow"),
        MetadataScreen(0, 32, "blue"),
        MetadataScreen(32, 32, "green"),
    ]

    mode = loop.add_mode()
    # mode.add_renderer(KirbyFlying())
    mode.add_renderer(KirbyFlying())
    # mode.add_renderer(KirbyLoop(64, 64))

    mode = loop.add_mode()
    mode.add_renderer(screens[0])
    mode.add_renderer(screens[1])
    mode.add_renderer(screens[2])
    mode.add_renderer(screens[3])
    
    if Environment.is_pi():
        # Start heart detection in another thread
        def my_function():
            # Your code to run in the separate thread goes here
            HeartRateSubscriber.get().run()

        # Create a new thread
        my_thread = threading.Thread(target=my_function)

        # Start the thread
        my_thread.start()
        
        def switch_fn():
            SwitchSubscriber.get().run()
            
        switch_thread = threading.Thread(target=switch_fn)
        switch_thread.start()

    loop.start()


if __name__ == "__main__":
    run()
