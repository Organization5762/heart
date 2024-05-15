import os
import logging
import platform

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from heart.display.renderers.kirby_loop import KirbyLoop
from heart.input.environment import GameLoop

logger = logging.getLogger(__name__)

def run():
    devices = []
    if platform.system() == "Linux":
        from heart.projects.rgb_display import LEDMatrix

        devices.append(LEDMatrix())

    screen_width, screen_height = 256, 256

    loop = GameLoop(screen_width, screen_height, devices=devices)

    loop.add_renderer(KirbyLoop(screen_width, screen_height))
    loop.start()


if __name__ == "__main__":
    run()
