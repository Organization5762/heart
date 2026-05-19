from dataclasses import dataclass

from heart.display.color import Color
from heart.navigation import ComposedRenderer
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color import RenderColor
from heart.renderers.spritesheet import SpritesheetLoop

KIRBY_SCENE_ASSETS = (
    "kirby_flying_32",
    "kirby_cell_64",
    "kirby_sleep_64",
    "tornado_kirby",
    "swimming_kirby",
    "running_kirby",
    "rolling_kirby",
    "fighting_kirby",
)


def kirby_spritesheet_scene(asset_name: str) -> ComposedRenderer:
    return ComposedRenderer(
        [
            RenderColor(Color(0, 0, 0)),
            SpritesheetLoop(
                sheet_file_path=f"{asset_name}.png",
                metadata_file_path=f"{asset_name}.json",
            ),
        ]
    )


@dataclass
class KirbyState:
    scenes: list[StatefulBaseRenderer]

    @staticmethod
    def build() -> "KirbyState":
        scenes = [kirby_spritesheet_scene(asset) for asset in KIRBY_SCENE_ASSETS]
        return KirbyState(scenes=scenes)
