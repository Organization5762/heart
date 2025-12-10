"""Beat detection debugging configuration.

Records audio and generates a click track for visualization in Audacity.
Left channel = original audio, Right channel = detected onset clicks.
"""

from heart.display.renderers.beat_flash import BeatFlashRenderer
from heart.environment import GameLoop

# Audio device - use "loopback" for system audio (BlackHole)
AUDIO_DEVICE = "loopback"

# Where to save the click track
OUTPUT_FILE = "~/Desktop/onset_clicks.wav"


def configure(loop: GameLoop) -> None:
    """Configure beat detection debugger."""
    mode = loop.add_mode("beat")
    mode.add_renderer(
        BeatFlashRenderer(
            sensitivity=1.0,
            device=AUDIO_DEVICE,
            output_file=OUTPUT_FILE,
        )
    )
    # Start directly in content mode (skip title selection)
    loop.app_controller.modes.state.in_select_mode = False
