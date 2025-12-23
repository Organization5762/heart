"""Validate behaviour of the SlidingImage renderer."""

import pygame

from heart.assets.loader import Loader
from heart.renderers.sliding_image import SlidingImage


def test_reset_preserves_cached_surface(monkeypatch, orientation, manager, stub_clock_factory) -> None:
    """Ensure SlidingImage keeps its cached surface across resets so scene transitions do not blank marquee banners."""

    base_surface = pygame.Surface((32, 8), pygame.SRCALPHA)
    base_surface.fill((10, 20, 30, 255))
    monkeypatch.setattr(Loader, "load", lambda _: base_surface)

    window = pygame.Surface((256, 64), pygame.SRCALPHA)
    clock = stub_clock_factory(0)

    renderer = SlidingImage("banner.png", speed=4)
    manager.window.on_next(window)
    renderer.initialize(window, clock, manager, orientation)
    manager.game_tick.on_next(True)

    initial_state = renderer.state
    assert initial_state.width == window.get_width()
    image_ref = renderer._image
    assert image_ref is not None

    window.fill((0, 0, 0, 0))
    offset_before = renderer.state.offset
    manager.game_tick.on_next(True)
    renderer.process(window, clock, manager, orientation)
    processed_state = renderer.state
    assert processed_state.offset == (
        offset_before + processed_state.speed
    ) % processed_state.width
    assert window.get_at((0, 0))[:3] == (10, 20, 30)


    renderer.reset()

    renderer.initialize(window, clock, manager, orientation)
    assert renderer._image is image_ref
    after_reset_state = renderer.state
    assert after_reset_state.offset == after_reset_state.speed
    assert after_reset_state.speed == 4
    manager.game_tick.on_next(True)
    assert renderer.state.width == processed_state.width

    window.fill((0, 0, 0, 0))
    offset_before_second = renderer.state.offset
    manager.game_tick.on_next(True)
    renderer.process(window, clock, manager, orientation)
    after_second_process_state = renderer.state
    assert after_second_process_state.offset == (
        offset_before_second + after_second_process_state.speed
    ) % after_second_process_state.width
    assert window.get_at((0, 0))[:3] == (10, 20, 30)
