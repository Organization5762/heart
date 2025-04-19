from heart.environment import GameLoop
from heart.display.renderers.metadata_screen import MetadataScreen


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(
        MetadataScreen(0, 0, "orange", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
    mode.add_renderer(
        MetadataScreen(32, 0, "blue", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
    mode.add_renderer(
        MetadataScreen(0, 32, "green", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
    mode.add_renderer(
        MetadataScreen(32, 32, "purple", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
