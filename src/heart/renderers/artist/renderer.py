from heart.display.color import Color
from heart.navigation import MultiScene
from heart.renderers import BaseRenderer
from heart.renderers.artist.provider import ArtistStateProvider
from heart.renderers.image import RenderImage
from heart.renderers.text import TextRendering


class ArtistScene(MultiScene):
    def __init__(self, provider: ArtistStateProvider | None = None) -> None:
        self._provider = provider or ArtistStateProvider()
        artist_state = self._provider.build()
        super().__init__(artist_state.scenes)

    @staticmethod
    def title_scene() -> list[BaseRenderer]:
        return [
            RenderImage(image_file="artist/imaginal_disk.png"),
            TextRendering(
                text=["artist"],
                font="Roboto",
                font_size=14,
                color=Color(255, 105, 180),
                y_location=32,
            ),
        ]
