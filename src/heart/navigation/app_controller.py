from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color import RenderColor
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.text import TextRendering
from heart.runtime.container import container
from heart.runtime.display_context import DisplayContext

from .composed_renderer import ComposedRenderer
from .game_modes import GameModes
from .multi_scene import MultiScene


@dataclass
class AppControllerState:
    pass


class AppController(StatefulBaseRenderer[AppControllerState]):
    def __init__(self) -> None:
        super().__init__()
        self.modes = GameModes()
        self.warmup = True
        self._renderer_resolver = container

    def _internal_device_display_mode(self) -> DeviceDisplayMode:
        return self.modes._internal_device_display_mode()

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> AppControllerState:
        self.modes.initialize(window, peripheral_manager, orientation)
        return AppControllerState()

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        return self.modes.get_renderers()

    def add_sleep_mode(self) -> None:
        sleep_title = [
            SpritesheetLoop(
                sheet_file_path="kirby_sleep_64.png",
                metadata_file_path="kirby_sleep_64.json",
                image_scale=0.5,
                offset_y=-5,
                disable_input=True,
            ),
            TextRendering(
                text=["sleep"],
                font="Grand9K Pixel.ttf",
                font_size=16,
                color=Color.kirby(),
                y_location=0.55,
            ),
        ]
        mode = self.add_mode(sleep_title)
        mode.add_renderer(RenderColor(Color(0, 0, 0)))

    def add_scene(self) -> MultiScene:
        new_scene = MultiScene(
            scenes=[],
            renderer_resolver=self._renderer_resolver,
        )
        title_renderer = self._build_title_renderer("Untitled")
        self.modes.add_new_pages(title_renderer, new_scene)
        return new_scene

    def add_mode(
        self,
        title: str
        | list[StatefulBaseRenderer | type[StatefulBaseRenderer]]
        | type[StatefulBaseRenderer]
        | StatefulBaseRenderer
        | None = None,
    ) -> ComposedRenderer:
        # TODO: Add a navigation page back in
        result = self._renderer_resolver.resolve(ComposedRenderer)
        if title is None:
            title = "Untitled"

        title_renderer = self._build_title_renderer(title)
        self.modes.add_new_pages(title_renderer, result)
        return result

    def is_empty(self) -> bool:
        return len(self.modes.state.renderers) == 0

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> Sequence[pygame.Surface]:
        raise NotImplementedError("AppController.real_process is not implemented")

    def _build_title_renderer(
        self,
        title: str
        | list[StatefulBaseRenderer | type[StatefulBaseRenderer]]
        | type[StatefulBaseRenderer]
        | StatefulBaseRenderer,
    ) -> StatefulBaseRenderer:
        if isinstance(title, str):
            return TextRendering(
                text=[title],
                font="Grand9K Pixel.ttf",
                font_size=12,
                color=Color(255, 105, 180),
                y_location=0.5,
            )
        if isinstance(title, list):
            composed = self._renderer_resolver.resolve(ComposedRenderer)
            composed.add_renderer(*title)
            return composed
        if isinstance(title, type) and issubclass(title, StatefulBaseRenderer):
            if self._renderer_resolver is None:
                raise ValueError("AppController requires a renderer resolver")
            return self._renderer_resolver.resolve(title)
        if isinstance(title, StatefulBaseRenderer):
            return title
        raise ValueError(f"Title must be a string or StatefulBaseRenderer, got: {title}")
