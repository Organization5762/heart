from heart.renderers.water_cube.renderer import WaterCube
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("water")
    mode.add_renderer(WaterCube)
