import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import logging
from heart.display.renderers.kirby import KirbyRunning
from heart.input.environment import GameLoop
from heart.projects.rgb_display import LEDMatrix
import platform

logger = logging.getLogger(__name__)

def run():
    devices = []
    if platform.system() == "Linux":
        devices.append(LEDMatrix())
    
    loop = GameLoop(
        64,
        64,
        devices=devices
    )
    
    loop.add_renderer(
        KirbyRunning()
    )
    loop.start()

if __name__ == "__main__":
    run()
    