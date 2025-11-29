"""Validate behaviour of the SlidingImage renderer."""

import pygame

from heart.assets.loader import Loader
from heart.display.renderers.sliding_image import SlidingImage


def test_reset_preserves_cached_surface(monkeypatch, orientation, manager, stub_clock_factory) -> None:
    """Ensure SlidingImage keeps its cached surface across resets so scene transitions do not blank marquee banners."""

    base_surface = pygame.Surface((32, 8), pygame.SRCALPHA)
    base_surface.fill((10, 20, 30, 255))
    monkeypatch.setattr(Loader, "load", lambda _: base_surface)

    window = pygame.Surface((256, 64), pygame.SRCALPHA)
    clock = stub_clock_factory(0)

    renderer = SlidingImage("banner.png", speed=4)
    renderer.initialize(window, clock, manager, orientation)

    initial_state = renderer.state
    assert initial_state.image is not None
    assert initial_state.width == window.get_width()
    image_ref = initial_state.image

    window.fill((0, 0, 0, 0))
    offset_before = renderer.state.offset
    renderer.process(window, clock, manager, orientation)
    processed_state = renderer.state
    assert processed_state.offset == (
        offset_before + processed_state.speed
    ) % processed_state.width
    assert window.get_at((0, 0))[:3] == (10, 20, 30)


    renderer.reset()

    after_reset_state = renderer.state
    assert after_reset_state.image is image_ref
    assert after_reset_state.width == processed_state.width
    assert after_reset_state.offset == 0
    assert after_reset_state.speed == 4

    window.fill((0, 0, 0, 0))
    offset_before_second = renderer.state.offset
    renderer.process(window, clock, manager, orientation)
    after_second_process_state = renderer.state
    assert after_second_process_state.offset == (
        offset_before_second + after_second_process_state.speed
    ) % after_second_process_state.width
    assert window.get_at((0, 0))[:3] == (10, 20, 30)
    assert after_second_process_state.image is image_ref
