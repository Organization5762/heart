import random
import time
from dataclasses import replace

from manyfold.architecture import PubSubObservable

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.peripheral.switch import SwitchState
from heart.renderers.yolisten.state import YoListenState
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class YoListenStateProvider(ObservableProvider[YoListenState]):
    def __init__(
        self,
        base_color: Color,
        *,
        base_scroll_speed: float,
        flicker_speed: float,
        flicker_intensity: float,
    ) -> None:
        self.base_color = base_color
        self.base_scroll_speed = base_scroll_speed
        self.flicker_speed = flicker_speed
        self.flicker_intensity = flicker_intensity

    def initial_state(self) -> YoListenState:
        return YoListenState(color=self.base_color, switch_state=None)

    def handle_switch_state(
        self, state: YoListenState, switch_state: SwitchState | None
    ) -> YoListenState:
        return replace(state, switch_state=switch_state)

    def calibrate_scroll_speed(self, state: YoListenState) -> YoListenState:
        rotation = 0.0
        if state.switch_state:
            rotation = state.switch_state.rotation_since_last_button_press
        return replace(state, scroll_speed_offset=rotation, should_calibrate=False)

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
                state, color=Color(r, g, b), last_flicker_update=current_time
            )
        return state

    def advance_word_position(
        self, state: YoListenState, *, scroll_speed: float, window_width: int
    ) -> YoListenState:
        if window_width <= 0:
            return state
        word_position = state.word_position - scroll_speed
        if word_position < -window_width:
            word_position = 0
        if word_position != state.word_position:
            return replace(state, word_position=word_position)
        return state

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> Variable[YoListenState]:
        initial_state = self.initial_state()
        switch_updates = peripheral_manager.input_io.main_switch_stream().map(
            lambda switch_event: (
                lambda state: self.handle_switch_state(
                    state, switch_event.state
                )
            )
        )
        window_widths = (
            peripheral_manager.window.filter(lambda window: window is not None)
            .map(lambda window: window.get_width())
            .distinct_until_changed()
            .start_with(0)
        )

        def advance(state: YoListenState, window_width: int) -> YoListenState:
            if state.should_calibrate:
                state = self.calibrate_scroll_speed(state)
            state = self.update_flicker(
                state,
                time.monotonic(),
                flicker_speed=self.flicker_speed,
                flicker_intensity=self.flicker_intensity,
            )
            scroll_speed = self.base_scroll_speed * self.scroll_speed_scale_factor(
                state
            )
            return self.advance_word_position(
                state, scroll_speed=scroll_speed, window_width=window_width
            )

        tick_updates = (
            peripheral_manager.input_io.frame_tick_stream()
            .with_latest_from(window_widths)
            .map(lambda latest: lambda state: advance(state, latest[1]))
        )
        return PubSubObservable.merge(switch_updates, tick_updates).state(
            initial_state,
            lambda state, update: update(state),
        )
