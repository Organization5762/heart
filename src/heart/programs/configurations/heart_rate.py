from heart.display.renderers.metadata_screen import MetadataScreen
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    print(f"adding metadata screens !!!")
    mode.add_renderer(
        MetadataScreen(0, 0, "orange", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
    mode.add_renderer(
        MetadataScreen(32, 0, "blue", "FF42ACF8-55E9-5A01-1D33-0A7A8EB0E0F3")
    )
    mode.add_renderer(
        MetadataScreen(0, 32, "green", "A145AA0D-F403-8B9C-34C6-D11601F9214E")
    )
    mode.add_renderer(
        MetadataScreen(32, 32, "purple", "A145AA0D-F403-8B9C-34C6-D11601F9214E")
    )
