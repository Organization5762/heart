from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Layout, Orientation
from heart.utilities.env import Configuration, RenderTileStrategy


class RendererSurfaceCache:
    def __init__(self) -> None:
        self._surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._tiled_surface_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._tile_positions_cache: dict[tuple[int, int, int, int], list[tuple[int, int]]] = {}

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
        if Configuration.render_surface_cache_enabled():
            cached = self._surface_cache.get(screen_size)
            if cached is None:
                cached = pygame.Surface(screen_size, pygame.SRCALPHA)
                self._surface_cache[screen_size] = cached
            else:
                cached.fill((0, 0, 0, 0))
            return cached
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
        if Configuration.render_surface_cache_enabled():
            cache_key = (tile_width, tile_height, rows, cols)
            tiled_surface = self._tiled_surface_cache.get(cache_key)
            if tiled_surface is None:
                tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)
                self._tiled_surface_cache[cache_key] = tiled_surface
            else:
                tiled_surface.fill((0, 0, 0, 0))
        else:
            tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)

        if Configuration.render_tile_strategy() == RenderTileStrategy.BLITS:
            positions_key = (tile_width, tile_height, rows, cols)
            positions = self._tile_positions_cache.get(positions_key)
            if positions is None:
                positions = [
                    (col * tile_width, row * tile_height)
                    for row in range(rows)
                    for col in range(cols)
                ]
                self._tile_positions_cache[positions_key] = positions
            tiled_surface.blits([(screen, pos) for pos in positions])
            return tiled_surface

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface
