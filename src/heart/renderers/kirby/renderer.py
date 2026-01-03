from heart.display.color import Color
from heart.navigation import MultiScene
from heart.renderers import StatefulBaseRenderer
from heart.renderers.kirby.state import KirbyState
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.text import TextRendering


class KirbyScene(MultiScene):
    def __init__(self) -> None:
        kirby_state = KirbyState.build()
        super().__init__(kirby_state.scenes)

    @staticmethod
    def title_scene() -> list[StatefulBaseRenderer]:
        return [
            SpritesheetLoop(
                sheet_file_path="kirby_flying_32.png",
                metadata_file_path="kirby_flying_32.json",
                image_scale=1 / 3,
                offset_y=-5,
                disable_input=True,
            ),
            TextRendering(
                text=["kirby mode"],
                font="Grand9K Pixel.ttf",
                font_size=12,
                color=Color.kirby(),
                y_location=0.65,
            ),
        ]
