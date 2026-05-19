from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pygame
import pygame.ftfont

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext


@dataclass(frozen=True)
class TextBlock:
    lines: list[pygame.Surface]
    width: int
    height: int


@dataclass(frozen=True)
class TitleScreenState:
    peripheral_manager: PeripheralManager


class TitleImageCentering(StrEnum):
    CENTER_RELATIVE = "center_relative"
    CENTER_ABSOLUTE = "center_absolute"


class TitleScreen(StatefulBaseRenderer[TitleScreenState]):
    def __init__(
        self,
        *,
        image_renderer: StatefulBaseRenderer,
        title: str,
        font: str = "Grand9K Pixel.ttf",
        font_size: int = 12,
        color: Color = Color(255, 105, 180),
        background: Color = Color(0, 0, 0),
        image_text_gap_px: int = 1,
        line_spacing_px: int = -4,
        text_bottom_margin_px: int = 2,
        image_centering: TitleImageCentering = TitleImageCentering.CENTER_RELATIVE,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.image_renderer = image_renderer
        self.title = title
        self.font = font
        self.font_size = font_size
        self.color = color
        self.background = background
        self.image_text_gap_px = image_text_gap_px
        self.line_spacing_px = line_spacing_px
        self.text_bottom_margin_px = text_bottom_margin_px
        self.image_centering = image_centering
        self._font: pygame.font.Font | None = None
        self._font_key: tuple[str, int] | None = None

    @property
    def name(self) -> str:
        return f"TitleScreen:{self.title}"

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        return [self]

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> TitleScreenState:
        del window, orientation
        return TitleScreenState(peripheral_manager=peripheral_manager)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            return

        window.fill(self.background._as_tuple())
        text_block = self._render_text_block()
        text_x = (window.get_width() - text_block.width) // 2
        text_y = window.get_height() - text_block.height - self.text_bottom_margin_px
        image_bottom = max(0, text_y - self.image_text_gap_px)

        image_surface = self._render_image(window, orientation)
        self._blit_image_centered_in_region(
            window=window,
            image_surface=image_surface,
            image_bottom=image_bottom,
        )
        self._blit_text_block(window, text_block, x=text_x, y=text_y)

    def _render_text_block(self) -> TextBlock:
        font = self._load_font()
        antialias = not self.font.endswith(".ttf")
        lines = [
            font.render(line, antialias, self.color._as_tuple())
            for line in self.title.splitlines()
        ]
        width = max((line.get_width() for line in lines), default=0)
        line_heights = [line.get_height() for line in lines]
        height = sum(line_heights)
        if len(lines) > 1:
            height += self.line_spacing_px * (len(lines) - 1)
        return TextBlock(lines=lines, width=width, height=max(0, height))

    def _load_font(self) -> pygame.font.Font:
        font_key = (self.font, self.font_size)
        if self._font is None or self._font_key != font_key:
            if self.font.endswith(".ttf"):
                self._font = Loader.load_font(self.font, font_size=self.font_size)
            else:
                self._font = pygame.ftfont.SysFont(self.font, self.font_size)
            self._font_key = font_key
        return self._font

    def _render_image(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> pygame.Surface:
        scratch_screen = pygame.Surface(window.get_size(), pygame.SRCALPHA)
        scratch = DisplayContext(
            device=window.device,
            screen=scratch_screen,
            clock=window.clock,
            last_render_mode=window.last_render_mode,
            can_configure_display=False,
        )
        scratch.fill((0, 0, 0, 0))
        if not self.image_renderer.initialized:
            self.image_renderer.initialize(
                window=scratch,
                peripheral_manager=self.state.peripheral_manager,
                orientation=orientation,
            )
        self.image_renderer._internal_process(
            window=scratch,
            peripheral_manager=self.state.peripheral_manager,
            orientation=orientation,
        )
        assert scratch.screen is not None
        return scratch.screen

    def _blit_image_centered_in_region(
        self,
        *,
        window: DisplayContext,
        image_surface: pygame.Surface,
        image_bottom: int,
    ) -> None:
        image_bounds = image_surface.get_bounding_rect(min_alpha=1)
        if image_bounds.width == 0 or image_bounds.height == 0:
            return
        if self.image_centering is TitleImageCentering.CENTER_ABSOLUTE:
            region_height = window.get_height()
        else:
            region_height = image_bottom
        region_height = max(1, region_height)
        target_x = window.get_width() // 2 - image_bounds.centerx
        target_y = region_height // 2 - image_bounds.centery
        window.blit(image_surface, (target_x, target_y))

    def _blit_text_block(
        self,
        window: DisplayContext,
        text_block: TextBlock,
        *,
        x: int,
        y: int,
    ) -> None:
        cursor_y = y
        for line in text_block.lines:
            line_x = x + (text_block.width - line.get_width()) // 2
            window.blit(line, (line_x, cursor_y))
            cursor_y += line.get_height() + self.line_spacing_px
