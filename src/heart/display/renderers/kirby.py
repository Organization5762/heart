from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.display.renderers.multi_scene import MultiScene
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering


class KirbyScene(MultiScene):
    def __init__(self) -> None:
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
        super().__init__(scenes)

    @staticmethod
    def title_scene() -> list[BaseRenderer]:
        return [
            TextRendering(
                text=["kirby mode"],
                font="Comic Sans MS",
                font_size=8,
                color=Color.kirby(),
                y_location=35,
            ),
            SpritesheetLoop(
                sheet_file_path=f"kirby_flying_32.png",
                metadata_file_path=f"kirby_flying_32.json",
                image_scale=1/3,
                offset_y=-5,
                disable_input=True,
            ),
        ]
