"""
This module implements a 3D glasses effect that remaps an image into
per-channel (red / cyan) components suitable for LED lenses. The
technique was developed in collaboration with Sri and Michael.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.three_d_glasses.provider import \
    ThreeDGlassesStateProvider
from heart.display.renderers.three_d_glasses.state import ThreeDGlassesState
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class _ChannelProfile:
    """Parameter bundle describing how to tint a specific frame."""

    red_shift: int
    cyan_shift: int
    red_gain: float
    cyan_gain: float


class ThreeDGlassesRenderer(AtomicBaseRenderer[ThreeDGlassesState]):
    """Render a sequence of images with a red/blue anaglyph effect."""

    def __init__(
        self,
        image_files: Sequence[str],
        *,
        frame_duration_ms: int = 650,
        builder: ThreeDGlassesStateProvider | None = None,
    ) -> None:
        if not image_files:
            raise ValueError("ThreeDGlassesRenderer requires at least one image file")

        super().__init__()
        self._builder = builder or ThreeDGlassesStateProvider(frame_duration_ms)
        self._image_files = list(image_files)
        self._images: list[pygame.Surface] = []
        self._image_arrays: list[np.ndarray] = []
        self._profiles: list[_ChannelProfile] = []
        self._effect_surface: pygame.Surface | None = None

    @staticmethod
    def _generate_profiles(count: int) -> list[_ChannelProfile]:
        """Create per-image tint profiles with distinct red/cyan balance."""

        if count <= 0:
            raise ValueError("Profile count must be positive")

        profiles: list[_ChannelProfile] = []
        # Cycle through pronounced horizontal parallax values while varying colour balance
        shift_pattern = (4, 6, 8, 5)
        denominator = max(count - 1, 1)

        for index in range(count):
            magnitude = shift_pattern[index % len(shift_pattern)]
            ratio = index / denominator
            red_gain = 0.9 + 0.4 * ratio
            cyan_gain = 1.2 - 0.3 * ratio
            profiles.append(
                _ChannelProfile(
                    red_shift=magnitude,
                    cyan_shift=-magnitude,
                    red_gain=red_gain,
                    cyan_gain=cyan_gain,
                )
            )

        return profiles

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

    @staticmethod
    def _clamp_shift(shift: int, width: int) -> int:
        """Limit channel shifts so small frames retain visible data."""

        if shift == 0 or width <= 1:
            return 0

        max_shift = min(abs(shift), width - 1)
        if max_shift == 0:
            return 0

        return max_shift if shift > 0 else -max_shift

    def _apply_profile(
        self, base_array: np.ndarray, profile: _ChannelProfile
    ) -> np.ndarray:
        """Convert RGB input to a red/cyan anaglyph frame."""

        left_eye = (
            base_array[..., 0] * 0.75
            + base_array[..., 1] * 0.20
            + base_array[..., 2] * 0.05
        )
        right_eye = (
            base_array[..., 1] * 0.55
            + base_array[..., 2] * 0.45
        )

        width = base_array.shape[0]
        red_shift = self._clamp_shift(profile.red_shift, width)
        cyan_shift = self._clamp_shift(profile.cyan_shift, width)

        red = self._shift_channel(left_eye, red_shift) * profile.red_gain
        cyan = self._shift_channel(right_eye, cyan_shift) * profile.cyan_gain

        frame = np.zeros_like(base_array)
        frame[..., 0] = red
        frame[..., 1] = cyan
        frame[..., 2] = cyan

        np.clip(frame, 0.0, 1.0, out=frame)
        return (frame * 255).astype(np.uint8)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        if not self._image_arrays:
            return

        next_state = self._builder.next_state(
            self.state,
            frame_count=len(self._image_arrays),
            elapsed_ms=float(clock.get_time()),
        )
        self.set_state(next_state)

        profile = self._profiles[next_state.current_index]
        base_array = self._image_arrays[next_state.current_index]

        frame_array = self._apply_profile(base_array, profile)

        assert self._effect_surface is not None
        pygame.surfarray.blit_array(self._effect_surface, frame_array)
        window.blit(self._effect_surface, (0, 0))

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ThreeDGlassesState:
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
        return self._builder.initial_state()
