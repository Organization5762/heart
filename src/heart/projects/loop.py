import os
from heart.display.renderers.kirby import KirbyFlying
from heart.display.renderers.text_render import TextRendering

from heart.input.heart_rate import HeartRateSubscriber
from heart.projects.mandelbrot import MandelbrotMode

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import threading
from heart.display.renderers.spritesheet_loop import SpritesheetLoop
from heart.input.env import Environment

from heart.input.switch import SwitchSubscriber

import logging
from heart.input.environment import GameLoop

logger = logging.getLogger(__name__)

def run():
    devices = []
    if Environment.is_pi():
        from heart.projects.rgb_display import LEDMatrix
        devices.append(LEDMatrix())

    height = width = 64
    loop = GameLoop(width, height, devices=devices)

    # 
    for kirby in [
        "kirby_flying_32",
        "kirby_cell_64",
        "kirby_sleep_64",
        "tornado_kirby",
        "swimming_kirby",
        "running_kirby",
        "rolling_kirby",
        "fighting_kirby",
    ]:
        mode = loop.add_mode()
        mode.add_renderer(
            SpritesheetLoop(
                screen_width=64,
                screen_height=64,
                sheet_file_path=f"{kirby}.png",
                metadata_file_path=f"{kirby}.json"
            )
        )

    modelbrot = loop.add_mode()
    modelbrot.add_renderer(
        MandelbrotMode(width, height)
    )

    mode = loop.add_mode()
    
    text = [
        "Lost my\nfriends\nagain"
    ]
    text.extend([
        f"Where's\n{name}" for name in [
            "Seb",
            "Cal",
            "Clem",
            "Michael",
            "Eric",
            "Faye",
            "Will",
            "Spriha",
            "Andrew",
            "Mel",
            "Stu",
            "Elena",
            "Jill",
            "Graham",
            "Russell",
            "Sam",
            "Sri"
        ]
    ])
    text.append("Where is\neveryone")
    mode.add_renderer(
        TextRendering(
            font='Comic Sans MS',
            font_size=12,
            color=(255, 105, 180),
            text=text
        )
    )
    
    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode
    loop.add_mode()

    ##
    # If on PI, start the sensors.  These should be stubbed out locally
    ##
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
