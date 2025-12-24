from dataclasses import dataclass

from heart.renderers import BaseRenderer
from heart.renderers.spritesheet import SpritesheetLoop


@dataclass
class KirbyState:
    scenes: list[BaseRenderer]

    @staticmethod
    def build() -> "KirbyState":
        scenes = [
            SpritesheetLoop(
                sheet_file_path=f"{kirby}.png",
                metadata_file_path=f"{kirby}.json",
            )
            for kirby in [
                "kirby_flying_32",
                "kirby_cell_64",
                "kirby_sleep_64",
                "tornado_kirby",
                "swimming_kirby",
                "running_kirby",
                "rolling_kirby",
                "fighting_kirby",
            ]
        ]
        return KirbyState(scenes=scenes)
