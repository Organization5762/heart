from __future__ import annotations

from heart.display.color import Color
from heart.renderers import BaseRenderer
from heart.renderers.kirby.state import KirbyState
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.text import TextRendering


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

    @staticmethod
    def title_renderers() -> list[BaseRenderer]:
        return [
            TextRendering(
                text=["kirby mode"],
                font="Roboto",
                font_size=14,
                color=Color.kirby(),
                y_location=35,
            ),
            SpritesheetLoop(
                sheet_file_path="kirby_flying_32.png",
                metadata_file_path="kirby_flying_32.json",
                image_scale=1 / 3,
                offset_y=-5,
                disable_input=True,
            ),
        ]
