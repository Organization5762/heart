import logging
from heart.display.renderers.kirby import KirbyRunning
from heart.input.environment import GameLoop
from heart.projects.rgb_display import LEDMatrix

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    loop = GameLoop(
        64,
        64,
        devices=[LEDMatrix()]
    )
    
    loop.add_renderer(
        KirbyRunning()
    )
    loop.start()
    
    