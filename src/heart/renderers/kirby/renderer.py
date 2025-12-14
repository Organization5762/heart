from heart.navigation import MultiScene
from heart.renderers import BaseRenderer
from heart.renderers.kirby.provider import KirbyStateProvider


class KirbyScene(MultiScene):
    def __init__(self, provider: KirbyStateProvider | None = None) -> None:
        self._provider = provider or KirbyStateProvider()
        kirby_state = self._provider.build()
        super().__init__(kirby_state.scenes)

    @staticmethod
    def title_scene() -> list[BaseRenderer]:
        return KirbyStateProvider.title_renderers()
