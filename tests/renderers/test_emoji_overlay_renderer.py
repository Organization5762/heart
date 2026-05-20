from __future__ import annotations

import random

import pygame
import pytest

from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.emoji_overlay import FloatingEmojiOverlayRenderer
from heart.runtime.display_context import DisplayContext


class TestFloatingEmojiOverlayRenderer:
    """Validate the phone-triggered emoji overlay animation."""

    def test_spawned_emoji_starts_at_bottom_and_floats_up(self, device) -> None:
        now = 10.0

        def _now() -> float:
            return now

        screen = pygame.Surface((256, 64), pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=screen, clock=pygame.time.Clock())
        renderer = FloatingEmojiOverlayRenderer(now=_now, rng=random.Random(1))
        renderer.initialize(window, PeripheralManager(), Rectangle.with_layout(4, 1))

        renderer.spawn("heart")
        renderer.real_process(window, device.orientation)
        initial_bounds = _alpha_bounds(screen)

        assert initial_bounds is not None
        assert initial_bounds.bottom >= 54

        now += 1.6
        renderer.real_process(window, device.orientation)
        midpoint_bounds = _alpha_bounds(screen)

        assert midpoint_bounds is not None
        assert midpoint_bounds.bottom < initial_bounds.bottom
        assert renderer.has_active_emojis()

        now += 2.0
        renderer.real_process(window, device.orientation)

        assert _alpha_bounds(screen) is None
        assert not renderer.has_active_emojis()

    def test_rejects_unsupported_emoji(self, device) -> None:
        screen = pygame.Surface((256, 64), pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=screen, clock=pygame.time.Clock())
        renderer = FloatingEmojiOverlayRenderer()
        renderer.initialize(window, PeripheralManager(), Rectangle.with_layout(4, 1))

        with pytest.raises(ValueError, match="Unsupported floating emoji"):
            renderer.spawn("bogus")

    def test_draws_rainbow_and_face_reactions(self, device) -> None:
        now = 10.0

        def _now() -> float:
            return now

        screen = pygame.Surface((256, 64), pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=screen, clock=pygame.time.Clock())
        renderer = FloatingEmojiOverlayRenderer(now=_now, rng=random.Random(2))
        renderer.initialize(window, PeripheralManager(), Rectangle.with_layout(4, 1))

        renderer.spawn("rainbow")
        renderer.spawn("seb")
        renderer.real_process(window, device.orientation)

        bounds = _alpha_bounds(screen)
        assert bounds is not None
        assert bounds.width > 20

    def test_caps_active_reactions_per_screen(self, device) -> None:
        now = 10.0

        def _now() -> float:
            return now

        screen = pygame.Surface((256, 64), pygame.SRCALPHA)
        window = DisplayContext(device=device, screen=screen, clock=pygame.time.Clock())
        renderer = FloatingEmojiOverlayRenderer(now=_now, rng=_CenteredRandom())
        renderer.initialize(window, PeripheralManager(), Rectangle.with_layout(4, 1))

        for _ in range(6):
            renderer.spawn("star")
            now += 0.01

        assert len(renderer._particles) == 5


def _alpha_bounds(surface: pygame.Surface) -> pygame.Rect | None:
    rects = pygame.mask.from_surface(surface, 1).get_bounding_rects()
    if not rects:
        return None
    bounds = rects[0].copy()
    for rect in rects[1:]:
        bounds.union_ip(rect)
    return bounds


class _CenteredRandom:
    def uniform(self, start: float, end: float) -> float:
        return (start + end) / 2
