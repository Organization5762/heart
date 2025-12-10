"""Beat-synced Ness animation mode.

Displays the Ness character with animation synced to detected music beats.
"""

from heart.display.renderers.beat_flash import BeatFlashRenderer
from heart.display.renderers.beat_sync_sprite import BeatSyncSprite
from heart.display.renderers.multicolor import MulticolorRenderer
from heart.environment import GameLoop
from heart.navigation import ComposedRenderer

# Audio device - use "loopback" for system audio (BlackHole)
AUDIO_DEVICE = "loopback"


def configure(loop: GameLoop) -> None:
    """Configure beat-synced shroomed mode."""
    mode = loop.add_mode("shroomed")
    mode.add_renderer(
        ComposedRenderer(
            [
                MulticolorRenderer(),
                # Beat detection (invisible - just updates shared beat state)
                BeatFlashRenderer(
                    sensitivity=1.0,
                    device=AUDIO_DEVICE,
                    render_flash=False,
                ),
                # Beat-synced Ness animation
                BeatSyncSprite("ness.png", frame_width=32, scale=2.0),
            ]
        )
    )
    # Start directly in content mode (skip title selection)
    loop.app_controller.modes.state.in_select_mode = False

