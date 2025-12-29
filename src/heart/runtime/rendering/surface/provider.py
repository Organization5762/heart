from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from heart import DeviceDisplayMode
from heart.device import Device, Layout, Orientation
from heart.runtime.rendering.display import DisplayModeManager
from heart.runtime.rendering.surface.cache import RendererSurfaceCache
from heart.utilities.env import Configuration, RenderTileStrategy

if TYPE_CHECKING:
    pass


class RendererSurfaceProvider:
    def __init__(
        self,
        device: Device,
        display_manager: DisplayModeManager | None = None,
        surface_cache: RendererSurfaceCache | None = None,
    ) -> None:
        self._display_manager = display_manager or DisplayModeManager(device)
        self._surface_cache = surface_cache or RendererSurfaceCache(device)

    def get_input_screen(
        self,
        window: pygame.Surface,
        orientation: Orientation,
        display_mode: DeviceDisplayMode,
    ) -> pygame.Surface:
        window_x, window_y = window.get_size()
        match display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL | DeviceDisplayMode.OPENGL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)
        return pygame.Surface(screen_size, pygame.SRCALPHA)

    def postprocess_input_screen(
        self,
        screen: pygame.Surface,
        orientation: Orientation,
        display_mode: DeviceDisplayMode,
    ) -> pygame.Surface:
        match display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen = self.tile_surface(
                    screen=screen, rows=layout.rows, cols=layout.columns
                )
            case DeviceDisplayMode.FULL:
                pass
        return screen

    def tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        target_size = (tile_width * cols, tile_height * rows)
        tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)

        if Configuration.render_tile_strategy() == RenderTileStrategy.BLITS:
            positions = [
                (col * tile_width, row * tile_height)
                for row in range(rows)
                for col in range(cols)
            ]
            tiled_surface.blits([(screen, pos) for pos in positions])
            return tiled_surface

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface
