import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from heart.assets import loader as assets_loader
from heart.device import Rectangle
from heart.display.renderers.three_d_glasses import ThreeDGlassesRenderer
from heart.peripheral.core.manager import PeripheralManager

class TestDisplayThreeDGlassesRenderer:
    """Group Display Three D Glasses Renderer tests so display three d glasses renderer behaviour stays reliable. This preserves confidence in display three d glasses renderer for end-to-end scenarios."""

    def test_renderer_requires_images(self) -> None:
        """Verify that ThreeDGlassesRenderer rejects initialization without input image paths. This avoids runtime crashes by catching configuration errors when wiring assets."""
        with pytest.raises(ValueError):
            ThreeDGlassesRenderer([])


    def test_generate_profiles_vary_shift_and_weights(self) -> None:
        """Verify that _generate_profiles returns profiles with distinct colour shifts and weights. This underpins depth perception accuracy so 3D rendering preserves the intended effect."""
        profiles = ThreeDGlassesRenderer._generate_profiles(4)

        assert len(profiles) == 4
        expected_shifts = (4, 6, 8, 5)
        assert [profile.red_shift for profile in profiles] == list(expected_shifts)
        assert profiles[0].red_gain < profiles[-1].red_gain
        assert profiles[0].cyan_gain > profiles[-1].cyan_gain



    def test_process_applies_anaglyph_and_cycles(self, monkeypatch: pytest.MonkeyPatch, stub_clock_factory) -> None:
        """Verify that process builds alternating anaglyph frames and advances once the frame duration elapses. This protects motion smoothness so the glasses experience remains comfortable."""
        window_size = (4, 4)
        window = pygame.Surface(window_size, pygame.SRCALPHA)
        orientation = Rectangle.with_layout(1, 1)
        manager = PeripheralManager()

        source_surfaces = [
            pygame.Surface(window_size, pygame.SRCALPHA),
            pygame.Surface(window_size, pygame.SRCALPHA),
        ]
        source_surfaces[0].fill((200, 120, 60, 255))
        source_surfaces[1].fill((40, 220, 160, 255))

        class _LoaderResult:
            def __init__(self, surface: pygame.Surface) -> None:
                self._surface = surface

            def convert_alpha(self) -> pygame.Surface:
                return self._surface

        load_calls = iter(_LoaderResult(surface) for surface in source_surfaces)
        monkeypatch.setattr(assets_loader.Loader, "load", lambda path: next(load_calls))

        clock = stub_clock_factory(0, 0, 150, repeat_last=False)
        renderer = ThreeDGlassesRenderer(["one.png", "two.png"], frame_duration_ms=120)

        renderer.initialize(window, clock, manager, orientation)

        renderer.process(window, clock, manager, orientation)
        frame_one = pygame.surfarray.array3d(window).copy()

        renderer.process(window, clock, manager, orientation)
        frame_two = pygame.surfarray.array3d(window).copy()

        assert np.array_equal(frame_one[..., 1], frame_one[..., 2])
        assert np.array_equal(frame_two[..., 1], frame_two[..., 2])
        assert np.any(frame_one[..., 0] > 0)
        assert np.any(frame_two[..., 2] > 0)
        assert not np.array_equal(frame_one, frame_two)
