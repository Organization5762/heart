"""Pixel similarity checks for slide-based renderers."""

from __future__ import annotations

from dataclasses import dataclass

import imagehash
import pygame
import pytest
from PIL import Image, ImageDraw

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.renderer import SlideTransitionRenderer
from heart.renderers.slide_transition.state import (SlideTransitionMode,
                                                    SlideTransitionState)
from heart.renderers.sliding_image.renderer import (SlidingImage,
                                                    SlidingRenderer)
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)
from heart.runtime.display_context import DisplayContext

HASH_DISTANCE_LIMIT = 4


@dataclass(frozen=True)
class _PatternState:
    background: tuple[int, int, int]
    accent: tuple[int, int, int]


class _PatternRenderer(StatefulBaseRenderer[_PatternState]):
    """Render a simple pattern so slide transforms are easy to verify."""

    def __init__(
        self,
        background: tuple[int, int, int],
        accent: tuple[int, int, int],
    ) -> None:
        super().__init__(state=_PatternState(background=background, accent=accent))
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        surface = (
            window.screen
            if isinstance(window, DisplayContext) and window.screen is not None
            else window
        )
        surface.fill(self.state.background)
        pygame.draw.rect(
            surface,
            self.state.accent,
            pygame.Rect(8, 8, 24, 24),
        )
        pygame.draw.rect(
            surface,
            self.state.accent,
            pygame.Rect(40, 16, 16, 32),
        )


def _surface_to_image(surface: pygame.Surface) -> Image.Image:
    array = pygame.surfarray.array3d(surface)
    return Image.fromarray(array.swapaxes(0, 1), "RGB")


def _assert_hash_similarity(
    observed: Image.Image,
    expected: Image.Image,
    *,
    limit: int = HASH_DISTANCE_LIMIT,
) -> None:
    observed_hash = imagehash.phash(observed)
    expected_hash = imagehash.phash(expected)
    distance = observed_hash - expected_hash
    assert distance <= limit, f"perceptual hash distance too high: {distance}"


def _build_striped_image(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
    ]
    stripe_width = size[0] // len(colors)
    for index, color in enumerate(colors):
        draw.rectangle(
            [index * stripe_width, 0, (index + 1) * stripe_width - 1, size[1]],
            fill=color,
        )
    return image


def _compose_slide_frame(
    base: Image.Image,
    *,
    offset: int,
) -> Image.Image:
    width, height = base.size
    frame = Image.new("RGB", (width, height))
    frame.paste(base, (-offset, 0))
    if offset:
        frame.paste(base, (width - offset, 0))
    return frame


class TestSlideRendererPixelSimilarity:
    """Validate slide renderers stay visually aligned via perceptual hashes."""

    def test_sliding_image_matches_expected_pixels(
        self,
        device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify SlidingImage matches a shifted image baseline so wrap logic stays correct."""
        size = device.scaled_display_size()
        base_image = _build_striped_image(size)
        renderer = SlidingImage("unused.png")
        renderer._image = pygame.image.fromstring(
            base_image.tobytes(),
            base_image.size,
            base_image.mode,
        )
        renderer.set_state(SlidingImageState(offset=16, speed=1, width=size[0]))
        renderer.initialized = True

        surface = pygame.Surface(size, pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=surface)

        renderer._internal_process(window, manager, orientation)

        observed = _surface_to_image(surface)
        expected = _compose_slide_frame(base_image, offset=16)
        _assert_hash_similarity(observed, expected)

    def test_sliding_renderer_matches_expected_pixels(
        self,
        device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify SlidingRenderer shifts composed output so wrapped frames remain consistent."""
        size = device.scaled_display_size()
        composed = _PatternRenderer(background=(5, 10, 20), accent=(220, 40, 60))
        surface = pygame.Surface(size, pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=surface)
        composed.initialize(window, manager, orientation)

        renderer = SlidingRenderer(composed)
        renderer.initialize(window, manager, orientation)
        renderer.set_state(SlidingRendererState(offset=12, speed=1, width=size[0]))

        renderer._internal_process(surface, manager, orientation)

        observed = _surface_to_image(surface)
        base = Image.new("RGB", size, composed.state.background)
        draw = ImageDraw.Draw(base)
        draw.rectangle([8, 8, 31, 31], fill=composed.state.accent)
        draw.rectangle([40, 16, 55, 47], fill=composed.state.accent)
        expected = _compose_slide_frame(base, offset=12)
        _assert_hash_similarity(observed, expected)

    @pytest.mark.parametrize(
        "fraction_offset",
        [0.25, 0.5],
        ids=["quarter", "half"],
    )
    def test_slide_transition_matches_expected_pixels(
        self,
        device,
        manager: PeripheralManager,
        orientation: Orientation,
        fraction_offset: float,
    ) -> None:
        """Verify SlideTransitionRenderer blends renderers by offset so transitions remain smooth."""
        size = device.scaled_display_size()
        renderer_a = _PatternRenderer(background=(10, 20, 30), accent=(200, 30, 80))
        renderer_b = _PatternRenderer(background=(20, 40, 60), accent=(30, 180, 140))
        renderer_a.set_state(_PatternState(background=(10, 20, 30), accent=(200, 30, 80)))
        renderer_a.initialized = True
        renderer_b.set_state(_PatternState(background=(20, 40, 60), accent=(30, 180, 140)))
        renderer_b.initialized = True
        provider = SlideTransitionProvider(
            renderer_a,
            renderer_b,
            direction=1,
            transition_mode=SlideTransitionMode.SLIDE,
        )
        renderer = SlideTransitionRenderer(provider)
        window = DisplayContext(device=device, screen=pygame.Surface(size, pygame.SRCALPHA))

        renderer.initialize(window, manager, orientation)
        renderer.set_state(
            SlideTransitionState(
                peripheral_manager=manager,
                fraction_offset=fraction_offset,
                sliding=True,
            )
        )
        renderer.initialized = True

        renderer._internal_process(window, manager, orientation)

        base_a = Image.new("RGB", size, renderer_a.state.background)
        draw_a = ImageDraw.Draw(base_a)
        draw_a.rectangle([8, 8, 31, 31], fill=renderer_a.state.accent)
        draw_a.rectangle([40, 16, 55, 47], fill=renderer_a.state.accent)
        base_b = Image.new("RGB", size, renderer_b.state.background)
        draw_b = ImageDraw.Draw(base_b)
        draw_b.rectangle([8, 8, 31, 31], fill=renderer_b.state.accent)
        draw_b.rectangle([40, 16, 55, 47], fill=renderer_b.state.accent)

        width = size[0]
        offset_a = int(-fraction_offset * width)
        offset_b = offset_a + width
        expected = Image.new("RGB", size)
        expected.paste(base_a, (offset_a, 0))
        expected.paste(base_b, (offset_b, 0))

        observed = _surface_to_image(window.screen)
        _assert_hash_similarity(observed, expected)
