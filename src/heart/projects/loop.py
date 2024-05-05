import logging, os
from heart.display.renderers.kirby import KirbyRunning
from heart.input.environment import GameLoop

if os.environ.get("LOCAL"):
    devices = []
else:
    from heart.projects.rgb_display import LEDMatrix

    devices = [LEDMatrix]

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    loop = GameLoop(64, 64, devices=devices)

    loop.add_renderer(KirbyRunning())
    loop.start()
