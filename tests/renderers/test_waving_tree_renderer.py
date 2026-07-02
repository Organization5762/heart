from __future__ import annotations

import pygame

from heart.device import Cube
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.waving_tree import WavingTreeRenderer
from heart.runtime.display_context import DisplayContext


def test_waving_tree_draws_visible_tree(device) -> None:
    orientation = Cube.sides()
    surface = pygame.Surface((256, 64), pygame.SRCALPHA)
    window = DisplayContext(
        device=device,
        screen=surface,
        clock=None,
        can_configure_display=False,
    )
    renderer = WavingTreeRenderer()

    renderer.real_process(window, orientation)

    green_pixels = _count_pixels_where(
        surface,
        lambda color: color.g > color.r and color.g > color.b and color.g > 70,
    )
    trunk_pixels = _count_pixels_where(
        surface,
        lambda color: color.r > color.g > color.b and color.r > 70,
    )

    assert green_pixels > 80
    assert trunk_pixels > 20


def test_waving_tree_branch_end_changes_with_breeze(device) -> None:
    orientation = Cube.sides()
    surface = pygame.Surface((256, 64), pygame.SRCALPHA)
    window = DisplayContext(
        device=device,
        screen=surface,
        clock=None,
        can_configure_display=False,
    )
    renderer = WavingTreeRenderer()
    renderer.initialize(window, PeripheralManager(), orientation)
    renderer._animation_start_s -= 1.0

    renderer.real_process(window, orientation)

    assert renderer.state > 0.0


def test_waving_tree_draws_falling_leaves(device) -> None:
    orientation = Cube.sides()
    surface = pygame.Surface((256, 64), pygame.SRCALPHA)
    window = DisplayContext(
        device=device,
        screen=surface,
        clock=None,
        can_configure_display=False,
    )
    renderer = WavingTreeRenderer()

    renderer.real_process(window, orientation)

    falling_leaf_pixels = _count_pixels_where(
        surface,
        lambda color: color.r > 150 and 70 < color.g < 190 and color.b < 90,
    )

    assert falling_leaf_pixels > 20


def test_falling_leaves_drift_over_time() -> None:
    first = pygame.Surface((256, 64), pygame.SRCALPHA)
    second = pygame.Surface((256, 64), pygame.SRCALPHA)

    WavingTreeRenderer._draw_falling_leaves(
        first,
        width=256,
        height=64,
        elapsed_s=0.0,
    )
    WavingTreeRenderer._draw_falling_leaves(
        second,
        width=256,
        height=64,
        elapsed_s=3.0,
    )

    assert pygame.image.tostring(first, "RGBA") != pygame.image.tostring(second, "RGBA")


def _count_pixels_where(surface: pygame.Surface, predicate) -> int:
    return sum(
        1
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if predicate(surface.get_at((x, y)))
    )
