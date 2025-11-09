from heart.display.renderers.three_d_glasses import ThreeDGlassesRenderer
from heart.environment import GameLoop

IMAGE_SEQUENCE = [
    "heart.png",
    "heart_16_big.png",
]


def configure(loop: GameLoop) -> None:
    """Attach the ThreeDGlassesRenderer for manual testing."""

    mode = loop.add_mode("3D Glasses Demo")
    mode.add_renderer(
        ThreeDGlassesRenderer(
            list(IMAGE_SEQUENCE),
            frame_duration_ms=650,
        )
    )
