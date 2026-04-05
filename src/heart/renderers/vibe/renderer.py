from heart.display.color import Color
from heart.navigation import MultiScene
from heart.renderers import StatefulBaseRenderer
from heart.renderers.text import TextRendering
from heart.renderers.vibe.state import VibeState


class VibeScene(MultiScene):
    def __init__(self) -> None:
        vibe_state = VibeState.build()
        super().__init__(vibe_state.scenes)

    @staticmethod
    def title_scene() -> list[StatefulBaseRenderer]:
        return [
            TextRendering(
                text=["vibe"],
                font="Grand9K Pixel.ttf",
                font_size=14,
                color=Color(255, 255, 255),
                y_location=0.5,
            ),
        ]
