from heart.display.color import Color
from heart.navigation import MultiScene
from heart.renderers import StatefulBaseRenderer
from heart.renderers.kirby.state import KirbyState
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.title_screen import TitleScreen


class KirbyScene(MultiScene):
    def __init__(self) -> None:
        kirby_state = KirbyState.build()
        super().__init__(kirby_state.scenes)

    @staticmethod
    def title_scene() -> list[StatefulBaseRenderer]:
        return [
            TitleScreen(
                image_renderer=SpritesheetLoop(
                    sheet_file_path="kirby_flying_32.png",
                    metadata_file_path="kirby_flying_32.json",
                    image_scale=1 / 3,
                    disable_input=True,
                ),
                title="kirby\nmode",
                color=Color.kirby(),
            ),
        ]
