from heart.display.renderers import BaseRenderer
from heart.display.renderers.artist.provider import ArtistStateProvider
from heart.navigation import MultiScene


class ArtistScene(MultiScene):
    def __init__(self, provider: ArtistStateProvider | None = None) -> None:
        self._provider = provider or ArtistStateProvider()
        artist_state = self._provider.build()
        super().__init__(artist_state.scenes)

    @staticmethod
    def title_scene() -> list[BaseRenderer]:
        return ArtistStateProvider.title_renderers()
