import logging
import random
from collections.abc import Callable
from dataclasses import replace

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers.yolisten.state import YoListenState

logger = logging.getLogger(__name__)


class YoListenStateProvider:
    def __init__(self, base_color: Color) -> None:
        self.base_color = base_color

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        on_switch_state: Callable[[SwitchState | None], None],
    ) -> YoListenState:
        def new_switch_state(value: SwitchState | None) -> None:
            on_switch_state(value)

        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=new_switch_state,
            on_error=lambda exc: logger.error("Error Occurred: %s", exc),
        )
        return YoListenState(color=self.base_color, switch_state=None)

    def handle_switch_state(
        self, state: YoListenState, switch_state: SwitchState | None
    ) -> YoListenState:
        return replace(state, switch_state=switch_state)

    def calibrate_scroll_speed(self, state: YoListenState) -> YoListenState:
        rotation = 0.0
        if state.switch_state:
            rotation = state.switch_state.rotation_since_last_button_press
        return replace(
            state,
            scroll_speed_offset=rotation,
            should_calibrate=False,
        )

    def scroll_speed_scale_factor(self, state: YoListenState) -> float:
        current_value = 0.0
        if state.switch_state:
            current_value = state.switch_state.rotation_since_last_button_press
        return 1.0 + (current_value - state.scroll_speed_offset) / 20.0

    def update_flicker(
        self,
        state: YoListenState,
        current_time: float,
        *,
        flicker_speed: float,
        flicker_intensity: float,
    ) -> YoListenState:
        if current_time - state.last_flicker_update >= flicker_speed:
            brightness_factor = 1 + random.uniform(
                -flicker_intensity, flicker_intensity
            )
            r = min(255, max(0, int(self.base_color.r * brightness_factor)))
            g = min(255, max(0, int(self.base_color.g * brightness_factor)))
            b = min(255, max(0, int(self.base_color.b * brightness_factor)))
            return replace(
                state,
                color=Color(r, g, b),
                last_flicker_update=current_time,
            )
        return state

    def advance_word_position(
        self, state: YoListenState, *, scroll_speed: float, window_width: int
    ) -> YoListenState:
        word_position = state.word_position - scroll_speed
        if word_position < -window_width:
            word_position = 0
        if word_position != state.word_position:
            return replace(state, word_position=word_position)
        return state
