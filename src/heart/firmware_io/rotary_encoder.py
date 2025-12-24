import time
from typing import Callable

from digitalio import Pull

from heart.firmware_io import constants

LONG_PRESS_DURATION_SECONDS = 0.5


# We don't use `json` here because the Trinkey doesn't support it by default
def form_json(name: str, data: int, producer_id: int):
    return (
        '{"event_type": "'
        + name
        + '", "data": '
        + str(data)
        + ', "producer_id": '
        + str(producer_id)
        + "}"
    )


class RotaryEncoderHandler:
    def __init__(
        self,
        encoder,
        switch,
        index=0,
        *,
        clock: Callable[[], float] | None = None,
    ):
        self.last_position = None
        self.press_started_timestamp = None
        self.long_pressed_sent = False
        self.encoder = encoder
        self.switch = switch
        self.index = index
        self._clock = clock or time.monotonic

    def _current_time(self):
        return self._clock()

    def _handle_switch(self):
        switch_is_pressed = self.switch.value

        # Depending on the pull direction we change the expected value
        if self.switch.pull == Pull.UP:
            switch_is_pressed = not switch_is_pressed

        if switch_is_pressed:
            # Button just pressed
            if self.press_started_timestamp is None:
                self.press_started_timestamp = self._current_time()
            else:
                # Button is still held down; check if it qualifies as a long press
                is_long_press = (
                    not self.long_pressed_sent
                    and (self._current_time() - self.press_started_timestamp)
                    >= LONG_PRESS_DURATION_SECONDS
                )
                if is_long_press:
                    yield form_json(constants.BUTTON_LONG_PRESS, 1, self.index)
                    self.long_pressed_sent = True
        else:
            # Button is released
            if self.press_started_timestamp is not None:
                if not self.long_pressed_sent:
                    yield form_json(constants.BUTTON_PRESS, 1, self.index)

                self.press_started_timestamp = None
                self.long_pressed_sent = False

    def _handle_rotation(self):
        position = self.encoder.position
        if self.last_position is None or position != self.last_position:
            yield form_json(constants.SWITCH_ROTATION, position, self.index)
        self.last_position = position

    def handle(self):
        yield from self._handle_rotation()
        yield from self._handle_switch()


class Seesaw:
    def __init__(self, handlers):
        self.handlers = handlers

    def handle(self):
        pooled: list[str] = []
        for handler in self.handlers:
            pooled.extend(handler.handle())
        for event in pooled:
            yield event
