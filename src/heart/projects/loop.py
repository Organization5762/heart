import os
import logging
import platform
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from heart.display.renderers.kirby_search import KirbySearch
from heart.input.environment import GameLoop
from heart.projects.rgb_display import LEDMatrix

logger = logging.getLogger(__name__)


def run():
    devices = []
    if platform.system() == "Linux":
        devices.append(LEDMatrix())
    screen_width, screen_height = 256, 256

    loop = GameLoop(
        screen_width,
        screen_height,
        devices=devices
    )
    
    loop.add_renderer(
        KirbySearch(screen_width, screen_height)
    )
    loop.start()


if __name__ == "__main__":
    run()

