"""Tests for the channel diffusion renderer rule application."""

import numpy as np
import pygame

from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.channel_diffusion import (ChannelDiffusionRenderer,
                                               ChannelDiffusionStateProvider)


class TestChannelDiffusionRenderer:
    """Validate channel diffusion spreads color energy predictably for troubleshooting."""

    def test_single_white_pixel_spreads_channels(self, stub_clock_factory) -> None:
        """Ensure a lone white pixel fans out by channel while dimming in place to keep the seed deterministic."""

        renderer = ChannelDiffusionRenderer(ChannelDiffusionStateProvider())
        manager = PeripheralManager()
        clock = stub_clock_factory(0)
        orientation = Rectangle.with_layout(1, 1)
        window = pygame.Surface((3, 3), pygame.SRCALPHA)

        renderer.initialize(window, clock, manager, orientation)

        initial_center = renderer.state.grid[1, 1]
        np.testing.assert_array_equal(initial_center, np.array([255, 255, 255], dtype=np.uint8))

        manager.game_tick.on_next(True)
        renderer.process(window, clock, manager, orientation)

        expected = np.zeros((3, 3, 3), dtype=np.uint8)
        expected[1, 1] = np.array([128, 128, 128], dtype=np.uint8)
        expected[1, 0] = np.array([0, 255, 0], dtype=np.uint8)
        expected[1, 2] = np.array([0, 255, 0], dtype=np.uint8)
        expected[0, 1] = np.array([0, 0, 255], dtype=np.uint8)
        expected[2, 1] = np.array([0, 0, 255], dtype=np.uint8)
        expected[0, 0] = np.array([255, 0, 0], dtype=np.uint8)
        expected[2, 0] = np.array([255, 0, 0], dtype=np.uint8)
        expected[0, 2] = np.array([255, 0, 0], dtype=np.uint8)
        expected[2, 2] = np.array([255, 0, 0], dtype=np.uint8)

        np.testing.assert_array_equal(renderer.state.grid, expected)
