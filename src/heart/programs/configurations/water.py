from heart.display.renderers.metadata_screen import MetadataScreen
from heart.display.renderers.water_cube import WaterCube
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("water")

    mode.add_renderer(WaterCube())
