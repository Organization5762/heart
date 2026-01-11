from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from heart import DeviceDisplayMode
from heart.device import Device, Layout, Orientation
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.cache import RendererSurfaceCache
from heart.utilities.env import Configuration, RenderTileStrategy

class RendererSurfaceProvider:
    def __init__(
        self,
        display_context: DisplayContext,
        surface_cache: RendererSurfaceCache | None = None,
    ) -> None:
        self._display_context = display_context
        self._surface_cache = surface_cache or RendererSurfaceCache(display_context)

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
