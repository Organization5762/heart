import pygame
import pytest

from heart.runtime.frame_exporter import FrameExporter
from heart.utilities.env import FrameExportStrategy


class TestFrameExporter:
    """Validate frame export strategies so device images stay correct and fast."""

    @pytest.mark.parametrize(
        ("strategy", "expected_mode"),
        [
            (FrameExportStrategy.BUFFER, "RGBA"),
            (FrameExportStrategy.ARRAY, "RGB"),
        ],
        ids=["buffer-path", "array-path"],
    )
    def test_export_preserves_pixel_orientation(
        self, strategy: FrameExportStrategy, expected_mode: str
    ) -> None:
        """Confirm exports keep pixel coordinates aligned so displays stay accurate."""

        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 255))
        surface.set_at((1, 0), (10, 20, 30, 255))
        surface.set_at((0, 1), (200, 180, 160, 255))

        exporter = FrameExporter(strategy_provider=lambda: strategy)
        image = exporter.export(surface)

        assert image.mode == expected_mode

        top_right = image.getpixel((1, 0))
        bottom_left = image.getpixel((0, 1))

        if strategy == FrameExportStrategy.BUFFER:
            assert top_right == (10, 20, 30, 255)
            assert bottom_left == (200, 180, 160, 255)
        else:
            assert top_right == (10, 20, 30)
            assert bottom_left == (200, 180, 160)
