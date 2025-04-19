from heart.display.renderers.multi_scene import MultiScene
from heart.display.renderers.spritesheet import SpritesheetLoop


class KirbyScene(MultiScene):
    def __init__(self) -> None:
        width = 64
        height = 64
        scenes = [
            SpritesheetLoop(
                screen_width=width,
                screen_height=height,
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
