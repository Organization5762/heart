from __future__ import annotations

from heart.renderers import BaseRenderer
from heart.renderers.kirby.state import KirbyState
from heart.renderers.spritesheet import SpritesheetLoop


class KirbyStateProvider:
    def build(self) -> KirbyState:
        scenes: list[BaseRenderer] = [
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
