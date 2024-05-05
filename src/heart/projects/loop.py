import logging
from src.heart.display.renderers.kirby import KirbyRunning
from src.heart.input.environment import GameLoop
#from heart.projects.rgb_display import LEDMatrix

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    loop = GameLoop(
        64,
        64,
        devices=[],
        #devices=[LEDMatrix()]
    )
    
    loop.add_renderer(
        KirbyRunning()
    )
    loop.start()
    
    