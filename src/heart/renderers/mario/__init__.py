from heart.peripheral.core.input import (AccelerometerController,
                                         AccelerometerDebugProfile)
from heart.peripheral.core.providers import register_singleton_provider
from heart.renderers.mario.provider import MarioRendererProvider
from heart.renderers.mario.renderer import MarioRenderer  # noqa: F401
from heart.renderers.mario.state import MarioRendererState  # noqa: F401

MARIO_METADATA_FILE_PATH = "mario_64.json"
MARIO_SHEET_FILE_PATH = "mario_64.png"

register_singleton_provider(
    MarioRendererProvider,
    lambda builder: MarioRendererProvider(
        accelerometer_controller=builder[AccelerometerController],
        accelerometer_debug_profile=builder[AccelerometerDebugProfile],
        sheet_file_path=MARIO_SHEET_FILE_PATH,
        metadata_file_path=MARIO_METADATA_FILE_PATH,
    ),
)
