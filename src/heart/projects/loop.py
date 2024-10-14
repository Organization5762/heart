import os

from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.display.renderers.text_render import TextRendering
from heart.input.heart_rate import HeartRateSubscriber

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import logging
import threading

from heart.display.renderers.pixel import Border, Rain, RandomPixel, Slinky
from heart.display.renderers.spritesheet_loop import SpritesheetLoop
from heart.input.env import Environment
from heart.input.environment import GameLoop
from heart.input.switch import SwitchSubscriber

logger = logging.getLogger(__name__)


def run():
    # TODO: Re-write this so that there is a local device, as this is broken on local atm
    device = None
    if Environment.is_pi():
        from heart.projects.rgb_display import LEDMatrix

        device = LEDMatrix(chain_length=8)

    height = width = 64
    loop = GameLoop(device=device)

    mode = loop.add_mode()
    for i in range(0, 100):
        mode.add_renderer(Rain())
        # mode.add_renderer(
        #     Slinky()
        # )
    # mode.add_renderer(
    #     RandomPixel(num_pixels=500)
    # )
    # mode.add_renderer(
    #     Border(
    #         border_width=2
    #     ),
    # )

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
                screen_width=width,
                screen_height=height,
                sheet_file_path=f"{kirby}.png",
                metadata_file_path=f"{kirby}.json",
            )
        )

    modelbrot = loop.add_mode()
    modelbrot.add_renderer(MandelbrotMode(width, height))

    mode = loop.add_mode()

    text = ["Lost my\nfriends\nagain"]
    text.extend(
        [
            f"Where's\n{name}"
            for name in [
                "seb",
                "cal",
                "clem",
                "michaēl",
                "eric",
                "faye",
                "big W",
                "spriha",
                "andrew",
                "mel",
                "stu",
                "elena",
                "jill",
                "graham",
                "russell",
                "sam",
                "sri",
            ]
        ]
    )
    text.append("Where is\neveryone")
    mode.add_renderer(
        TextRendering(
            font="Comic Sans MS", font_size=20, color=(255, 105, 180), text=text
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
