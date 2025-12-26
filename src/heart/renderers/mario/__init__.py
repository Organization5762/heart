from lagom import Singleton

from heart.peripheral.core.providers import register_provider
from heart.peripheral.providers.acceleration import AllAccelerometersProvider
from heart.renderers.mario.provider import MarioRendererProvider
from heart.renderers.mario.renderer import MarioRenderer  # noqa: F401
from heart.renderers.mario.state import MarioRendererState  # noqa: F401

MARIO_METADATA_FILE_PATH = "mario_64.json"
MARIO_SHEET_FILE_PATH = "mario_64.png"

register_provider(
    MarioRendererProvider,
    Singleton(
        lambda builder: MarioRendererProvider(
            accel_stream=builder[AllAccelerometersProvider],
            sheet_file_path=MARIO_SHEET_FILE_PATH,
            metadata_file_path=MARIO_METADATA_FILE_PATH,
        )
    ),
)
