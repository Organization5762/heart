"""Renderer for LED anaglyph imagery.

This module implements a 3D glasses effect that remaps an image into
per-channel (red / blue) components suitable for LED lenses. The
technique was developed in collaboration with Sri and Michael.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class _ChannelProfile:
    """Parameter bundle describing how to tint a specific frame."""

    red_shift: int
    blue_shift: int
    red_weight: float
    blue_weight: float


class ThreeDGlassesRenderer(BaseRenderer):
    """Render a sequence of images with a red/blue anaglyph effect."""

    def __init__(
        self,
        image_files: Sequence[str],
        *,
        frame_duration_ms: int = 650,
    ) -> None:
        super().__init__()
        if not image_files:
            raise ValueError("ThreeDGlassesRenderer requires at least one image file")

        self._image_files = list(image_files)
        self._frame_duration_ms = frame_duration_ms

        self._images: list[pygame.Surface] = []
        self._image_arrays: list[np.ndarray] = []
        self._profiles: list[_ChannelProfile] = []
        self._effect_surface: pygame.Surface | None = None

        self._current_index = 0
        self._elapsed_ms = 0

    @staticmethod
    def _generate_profiles(count: int) -> list[_ChannelProfile]:
        """Create per-image tint profiles with distinct red/blue balance."""

        if count <= 0:
            raise ValueError("Profile count must be positive")

        profiles: list[_ChannelProfile] = []
        # Cycle through gentle horizontal parallax values while varying colour balance
        shift_pattern = (1, 2, 3)
        denominator = max(count - 1, 1)

        for index in range(count):
            magnitude = shift_pattern[index % len(shift_pattern)]
            ratio = index / denominator
            red_weight = 0.55 + 0.35 * ratio
            blue_weight = 0.95 - 0.35 * ratio
            profiles.append(
                _ChannelProfile(
                    red_shift=magnitude,
                    blue_shift=-magnitude,
                    red_weight=red_weight,
                    blue_weight=blue_weight,
                )
            )

        return profiles

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        window_size = window.get_size()

        self._images.clear()
        self._image_arrays.clear()

        for file_path in self._image_files:
            surface = Loader.load(file_path).convert_alpha()
            surface = pygame.transform.smoothscale(surface, window_size)
            self._images.append(surface)

            array = pygame.surfarray.array3d(surface).astype(np.float32) / 255.0
            self._image_arrays.append(array)

        self._profiles = self._generate_profiles(len(self._image_arrays))
        self._effect_surface = pygame.Surface(window_size, pygame.SRCALPHA)

        self._current_index = 0
        self._elapsed_ms = 0

        super().initialize(window, clock, peripheral_manager, orientation)

    @staticmethod
    def _shift_channel(channel: np.ndarray, shift: int) -> np.ndarray:
        """Roll channel data horizontally while blanking the wrapped pixels."""

        if shift == 0:
            return channel

        shifted = np.roll(channel, shift=shift, axis=0)
        if shift > 0:
            shifted[:shift, :] = 0.0
        else:
            shifted[shift:, :] = 0.0
        return shifted

    def _apply_profile(
        self, base_array: np.ndarray, profile: _ChannelProfile
    ) -> np.ndarray:
        """Convert RGB input to a red/blue anaglyph frame."""

        grayscale = (
            base_array[..., 0] * 0.299
            + base_array[..., 1] * 0.587
            + base_array[..., 2] * 0.114
        )

        red = self._shift_channel(grayscale, profile.red_shift) * profile.red_weight
        blue = self._shift_channel(grayscale, profile.blue_shift) * profile.blue_weight

        frame = np.zeros_like(base_array)
        frame[..., 0] = red
        frame[..., 2] = blue

        np.clip(frame, 0.0, 1.0, out=frame)
        return (frame * 255).astype(np.uint8)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self._image_arrays:
            return

        self._elapsed_ms += clock.get_time()
        if self._elapsed_ms >= self._frame_duration_ms:
            self._elapsed_ms %= self._frame_duration_ms
            self._current_index = (self._current_index + 1) % len(self._image_arrays)

        profile = self._profiles[self._current_index]
        base_array = self._image_arrays[self._current_index]

        frame_array = self._apply_profile(base_array, profile)

        assert self._effect_surface is not None
        pygame.surfarray.blit_array(self._effect_surface, frame_array)
        window.blit(self._effect_surface, (0, 0))
