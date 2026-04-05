from heart.display.renderers.crabdance import (CrabDanceLaserBackground,
                                               ControlledCrabDance)
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("crabdance")
    mode.add_title_renderer(
        CrabDanceLaserBackground(),
        ControlledCrabDance(image_scale=0.8, offset_y=-2),
    )
    mode.add_renderer(
        CrabDanceLaserBackground(),
        ControlledCrabDance(image_scale=0.92, offset_y=-1),
    )
