from __future__ import annotations

import math
import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

SKY_TOP = (7, 18, 34)
SKY_BOTTOM = (43, 72, 88)
GROUND_TOP = (22, 58, 40)
GROUND_BOTTOM = (8, 31, 24)
TRUNK_DARK = (74, 41, 24)
TRUNK_LIGHT = (138, 82, 45)
LEAF_DARK = (23, 90, 56)
LEAF_MID = (52, 150, 74)
LEAF_LIGHT = (135, 213, 105)
FALL_LEAF_GOLD = (227, 167, 66)
FALL_LEAF_ORANGE = (199, 102, 45)
FALL_LEAF_GREEN = (111, 178, 80)
FLOWER_COLOR = (255, 183, 116)
TREE_DEPTHS = 5
FALLING_LEAF_COUNT = 18


class WavingTreeRenderer(StatefulBaseRenderer[float]):
    """Render a stylized tree waving in a gentle breeze."""

    def __init__(self) -> None:
        super().__init__(state=0.0)
        self.device_display_mode = DeviceDisplayMode.FULL
        self._animation_start_s = time.monotonic()

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> float:
        del window, peripheral_manager, orientation
        return 0.0

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        elapsed_s = time.monotonic() - self._animation_start_s
        width, height = window.get_size()
        self.set_state(elapsed_s)
        self._draw_background(
            window.screen, width=width, height=height, elapsed_s=elapsed_s
        )
        root = (width // 2, height - max(5, height // 9))
        trunk_length = height * 0.48
        sway = math.sin(elapsed_s * 0.78) * 0.18
        self._draw_branch(
            window.screen,
            start=root,
            length=trunk_length,
            angle=-math.pi / 2 + sway * 0.38,
            depth=TREE_DEPTHS,
            elapsed_s=elapsed_s,
            phase=0.0,
        )
        self._draw_leaf_canopy(
            window.screen,
            center=(width // 2, round(height * 0.34)),
            elapsed_s=elapsed_s,
        )
        self._draw_falling_leaves(
            window.screen,
            width=width,
            height=height,
            elapsed_s=elapsed_s,
        )
        self._draw_grass(window.screen, width=width, height=height, elapsed_s=elapsed_s)

    @staticmethod
    def _draw_background(
        screen: pygame.Surface,
        *,
        width: int,
        height: int,
        elapsed_s: float,
    ) -> None:
        horizon = int(height * 0.82)
        for y in range(horizon):
            ratio = y / max(horizon - 1, 1)
            color = _mix_color(SKY_TOP, SKY_BOTTOM, ratio)
            pygame.draw.line(screen, color, (0, y), (width, y))
        for y in range(horizon, height):
            ratio = (y - horizon) / max(height - horizon - 1, 1)
            color = _mix_color(GROUND_TOP, GROUND_BOTTOM, ratio)
            pygame.draw.line(screen, color, (0, y), (width, y))
        moon_x = int(width * 0.13)
        moon_y = max(6, int(height * 0.18))
        pygame.draw.circle(screen, (255, 226, 164), (moon_x, moon_y), 4)
        pygame.draw.circle(screen, SKY_TOP, (moon_x + 2, moon_y - 1), 3)
        for x in range(0, width, 21):
            y = 7 + ((x * 17) % max(horizon - 10, 1))
            shimmer = int((math.sin(elapsed_s + x * 0.11) + 1.0) * 16)
            screen.set_at((x, y), (56 + shimmer, 90 + shimmer, 113 + shimmer))

    def _draw_branch(
        self,
        screen: pygame.Surface,
        *,
        start: tuple[int, int],
        length: float,
        angle: float,
        depth: int,
        elapsed_s: float,
        phase: float,
    ) -> None:
        wind = math.sin(elapsed_s * 1.25 + phase) * (0.12 + depth * 0.012)
        angle += wind
        end = (
            round(start[0] + math.cos(angle) * length),
            round(start[1] + math.sin(angle) * length),
        )
        width = max(1, depth)
        bark_color = _mix_color(TRUNK_LIGHT, TRUNK_DARK, depth / TREE_DEPTHS)
        pygame.draw.line(screen, TRUNK_DARK, start, end, width + 1)
        pygame.draw.line(screen, bark_color, start, end, width)
        if depth <= 2:
            self._draw_leaf_cluster(
                screen,
                center=end,
                elapsed_s=elapsed_s,
                phase=phase,
                radius=3 if depth == 2 else 2,
            )
        if depth <= 1:
            return

        next_length = length * 0.68
        split = 0.34 + math.sin(phase * 1.7) * 0.08
        self._draw_branch(
            screen,
            start=end,
            length=next_length,
            angle=angle - split,
            depth=depth - 1,
            elapsed_s=elapsed_s,
            phase=phase + 1.3,
        )
        self._draw_branch(
            screen,
            start=end,
            length=next_length * 0.94,
            angle=angle + split * 0.92,
            depth=depth - 1,
            elapsed_s=elapsed_s,
            phase=phase + 2.1,
        )
        if depth >= 3:
            self._draw_branch(
                screen,
                start=end,
                length=next_length * 0.72,
                angle=angle + math.sin(phase + 0.4) * 0.38,
                depth=depth - 2,
                elapsed_s=elapsed_s,
                phase=phase + 3.2,
            )

    @staticmethod
    def _draw_leaf_cluster(
        screen: pygame.Surface,
        *,
        center: tuple[int, int],
        elapsed_s: float,
        phase: float,
        radius: int = 2,
    ) -> None:
        offsets = (
            (0, 0),
            (-3, 1),
            (3, -1),
            (-1, -3),
            (2, 3),
            (-5, -1),
            (5, 2),
            (0, 5),
        )
        colors = (
            LEAF_DARK,
            LEAF_MID,
            LEAF_LIGHT,
            LEAF_MID,
            LEAF_DARK,
            LEAF_MID,
            LEAF_LIGHT,
            LEAF_DARK,
        )
        for index, offset in enumerate(offsets):
            sway_x = round(math.sin(elapsed_s * 1.7 + phase + index) * 1.5)
            leaf_center = (
                center[0] + offset[0] + sway_x,
                center[1] + offset[1],
            )
            pygame.draw.circle(screen, colors[index], leaf_center, radius)
        if int((phase * 10) % 5) == 0:
            pygame.draw.circle(screen, FLOWER_COLOR, (center[0] + 1, center[1]), 1)

    @staticmethod
    def _draw_leaf_canopy(
        screen: pygame.Surface,
        *,
        center: tuple[int, int],
        elapsed_s: float,
    ) -> None:
        blobs = (
            (-24, 3, 7, LEAF_DARK, 0.1),
            (-18, -5, 8, LEAF_MID, 0.8),
            (-10, 1, 9, LEAF_LIGHT, 1.4),
            (-2, -8, 8, LEAF_MID, 2.2),
            (8, -2, 9, LEAF_DARK, 2.8),
            (17, 4, 8, LEAF_MID, 3.5),
            (25, -4, 6, LEAF_LIGHT, 4.0),
            (-7, 9, 8, LEAF_DARK, 4.9),
            (10, 10, 7, LEAF_MID, 5.5),
        )
        for offset_x, offset_y, radius, color, phase in blobs:
            sway_x = round(math.sin(elapsed_s * 1.15 + phase) * 3)
            sway_y = round(math.cos(elapsed_s * 0.9 + phase) * 1)
            pygame.draw.circle(
                screen,
                color,
                (center[0] + offset_x + sway_x, center[1] + offset_y + sway_y),
                radius,
            )
        for index, x_offset in enumerate(range(-28, 31, 7)):
            phase = index * 0.73
            y_offset = round(math.sin(index * 1.3) * 7)
            leaf_center = (
                center[0] + x_offset + round(math.sin(elapsed_s * 1.8 + phase) * 2),
                center[1] + y_offset + round(math.cos(elapsed_s + phase) * 2),
            )
            color = (LEAF_LIGHT, LEAF_MID, LEAF_DARK)[index % 3]
            pygame.draw.circle(screen, color, leaf_center, 2)

    @staticmethod
    def _draw_grass(
        screen: pygame.Surface,
        *,
        width: int,
        height: int,
        elapsed_s: float,
    ) -> None:
        ground_y = height - max(3, height // 10)
        for x in range(0, width, 4):
            blade_height = 3 + (x * 7) % 5
            sway = round(math.sin(elapsed_s * 1.6 + x * 0.23) * 2)
            color = LEAF_MID if x % 8 == 0 else LEAF_DARK
            pygame.draw.line(
                screen,
                color,
                (x, height - 1),
                (x + sway, ground_y - blade_height),
                1,
            )

    @staticmethod
    def _draw_falling_leaves(
        screen: pygame.Surface,
        *,
        width: int,
        height: int,
        elapsed_s: float,
    ) -> None:
        fall_top = max(8, int(height * 0.2))
        fall_height = max(1, int(height * 0.72) - fall_top)
        tree_center_x = width * 0.5
        colors = (FALL_LEAF_GOLD, FALL_LEAF_ORANGE, FALL_LEAF_GREEN, LEAF_LIGHT)

        for index in range(FALLING_LEAF_COUNT):
            seed = index * 37
            speed = 0.055 + (index % 5) * 0.012
            progress = (elapsed_s * speed + (index * 0.071)) % 1.0
            source_x = tree_center_x + ((seed % 57) - 28) * (width / 256)
            wind = math.sin(elapsed_s * 0.72 + index * 0.63) * (width * 0.075)
            flutter = math.sin(elapsed_s * 4.1 + index * 1.9) * 2.4
            x = round(source_x + wind + flutter + progress * width * 0.09)
            y = round(fall_top + progress * fall_height)
            if x < -3 or x >= width + 3:
                continue

            color = colors[index % len(colors)]
            tilt = math.sin(elapsed_s * 5.2 + index)
            WavingTreeRenderer._draw_falling_leaf(
                screen,
                center=(x, y),
                color=color,
                tilt=tilt,
            )

    @staticmethod
    def _draw_falling_leaf(
        screen: pygame.Surface,
        *,
        center: tuple[int, int],
        color: tuple[int, int, int],
        tilt: float,
    ) -> None:
        x, y = center
        if tilt >= 0:
            points = ((x - 2, y), (x, y - 2), (x + 3, y), (x, y + 2))
            stem_end = (x + 2, y + 2)
        else:
            points = ((x - 3, y), (x, y - 2), (x + 2, y), (x, y + 2))
            stem_end = (x - 2, y + 2)
        pygame.draw.polygon(screen, color, points)
        pygame.draw.line(screen, TRUNK_LIGHT, (x, y), stem_end, 1)


def _mix_color(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    ratio = max(0.0, min(1.0, ratio))
    return tuple(
        round(first[index] * (1.0 - ratio) + second[index] * ratio)
        for index in range(3)
    )
