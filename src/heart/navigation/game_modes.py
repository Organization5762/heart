from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

if TYPE_CHECKING:
    from heart.renderers.slide_transition import SlideTransitionRenderer


@dataclass
class GameModeState:
    title_renderers: list[StatefulBaseRenderer] = field(default_factory=list)
    renderers: list[StatefulBaseRenderer] = field(default_factory=list)
    in_select_mode: bool = True
    last_long_button_value: int = 0
    mode_offset: int = 0
    _active_mode_index: int = 0
    previous_mode_index: int = 0
    sliding_transition: SlideTransitionRenderer | None = None

    def active_renderer(self) -> StatefulBaseRenderer:
        assert len(self.renderers) > 0, "Must have at least one renderer to select from"
        offset = self._active_mode_index + self.mode_offset
        mode_index = offset % len(self.renderers)
        last_scene_index = self.previous_mode_index

        if last_scene_index != mode_index:
            from heart.navigation import (  # avoids circular imports for patching
                SlideTransitionProvider, SlideTransitionRenderer)

            slide_dir = self._resolve_slide_direction(last_scene_index, mode_index)
            provider = SlideTransitionProvider(
                renderer_a=self.title_renderers[last_scene_index],
                renderer_b=self.title_renderers[mode_index],
                direction=slide_dir,
            )
            self.sliding_transition = SlideTransitionRenderer(provider)
            self.previous_mode_index = mode_index
            return self.sliding_transition

        if self.sliding_transition is not None:
            if self.sliding_transition.is_done():
                self.sliding_transition = None
            else:
                return self.sliding_transition

        if self.in_select_mode:
            return self.title_renderers[mode_index]

        self.previous_mode_index = mode_index
        return self.renderers[mode_index]

    def _resolve_slide_direction(self, last_scene_index: int, mode_index: int) -> int:
        if self.mode_offset > 0:
            return 1
        if self.mode_offset < 0:
            return -1
        forward_steps = (mode_index - last_scene_index) % len(self.renderers)
        backward_steps = (last_scene_index - mode_index) % len(self.renderers)
        return 1 if forward_steps <= backward_steps else -1


class GameModes(StatefulBaseRenderer[GameModeState]):
    """GameModes represents a collection of modes in the game loop where different
    renderers can be added.

    Navigation is built-in to this, assuming the user long-presses.
    """

    def __init__(self) -> None:
        super().__init__()
        self._init_context: tuple[
            pygame.Surface,
            pygame.time.Clock,
            PeripheralManager,
            Orientation,
        ] | None = None
        # TODO: Fix this wonkiness
        self.device_display_mode = None

    def _internal_device_display_mode(self) -> DeviceDisplayMode:
        renderers = self.state.renderers + self.state.title_renderers
        if any(
            renderer.device_display_mode == DeviceDisplayMode.OPENGL
            for renderer in renderers
        ):
            return DeviceDisplayMode.OPENGL
        return DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> GameModeState:
        self._init_context = (window, peripheral_manager, orientation)
        if self._state is not None:
            self._initialize_registered_renderers(
                window, peripheral_manager, orientation
            )
            state = self._state
        else:
            state = GameModeState()
        peripheral_manager.get_main_switch_subscription().subscribe(
            on_next=self.handle_state,
        )
        return state

    def add_new_pages(
        self, title_renderer: StatefulBaseRenderer, renderers: StatefulBaseRenderer
    ) -> None:
        if self._state is None:
            self.set_state(GameModeState())
        self.state.renderers.append(renderers)
        self.state.title_renderers.append(title_renderer)
        if self.is_initialized() and self._init_context is not None:
            window, clock, peripheral_manager, orientation = self._init_context
            title_renderer.initialize(window, peripheral_manager, orientation)
            renderers.initialize(window, peripheral_manager, orientation)

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        active_renderer = self.state.active_renderer()
        return active_renderer.get_renderers()

    def real_process(
        self, window: DisplayContext, orientation: Orientation
    ) -> None:
        raise NotImplementedError("GameModes.real_process is not implemented")

    def handle_state(self, input: SwitchState) -> None:
        new_long_button_value = input.long_button_value
        if new_long_button_value != self.state.last_long_button_value:
            if self.state.in_select_mode:
                self.state._active_mode_index += self.state.mode_offset
                self.state.mode_offset = 0
            else:
                for renderer in self.state.renderers:
                    renderer.reset()

            self.state.in_select_mode = not self.state.in_select_mode
            self.state.last_long_button_value = new_long_button_value

        if self.state.in_select_mode:
            self.state.mode_offset = input.rotation_since_last_long_button_press

    def _initialize_registered_renderers(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Renderers nmay have different display modes, so we need to initialize them all
        for renderer in self.state.renderers:
            window.configure_window(renderer.device_display_mode)
            renderer.initialize(window, peripheral_manager, orientation)
        for renderer in self.state.title_renderers:
            window.configure_window(renderer.device_display_mode)
            renderer.initialize(window, peripheral_manager, orientation)
