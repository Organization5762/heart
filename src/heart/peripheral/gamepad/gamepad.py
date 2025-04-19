import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Iterator

import pygame.joystick
from pygame.event import Event

from heart.peripheral import Peripheral
from heart.utilities.env import REQUEST_JOYSTICK_MODULE_RESET

logger = logging.getLogger(__name__)


class GamepadIdentifier(Enum):
    # string values need to exactly match what's reported from joystick.get_name()
    # so check that first when adding a controller type
    BIT_DO_LITE_2 = "8BitDo Lite 2"
    SWITCH_PRO = "Nintendo Switch Pro Controller"


class Gamepad(Peripheral):
    def __init__(
        self, joystick_id: int = 0, joystick: pygame.joystick.JoystickType | None = None
    ):
        self.joystick_id = joystick_id
        self.joystick = joystick
        self.TAP_THRESHOLD_MS = 500

        self._num_buttons: int = None
        self._num_axes: int = None
        self._press_time = {}
        self._tap_flag = defaultdict(bool)
        self._pressed_prev_frame = defaultdict(bool)
        self._pressed_curr_frame = defaultdict(bool)
        self._axis_prev_frame = defaultdict(float)
        self._axis_curr_frame = defaultdict(float)

    def is_held(self, button_id: int) -> bool:
        return self._pressed_curr_frame[button_id]

    def was_tapped(self, button_id: int) -> bool:
        tapped = self._tap_flag[button_id]
        self._tap_flag[button_id] = False
        return tapped

    def was_released(self, button_id: int) -> bool:
        return (
            not self._pressed_curr_frame[button_id]
            and self._pressed_prev_frame[button_id]
        )

    def axis_value(self, axis_id: int, dead_zone: float = 0) -> float:
        axis_value = self._axis_curr_frame[self.axis_key(axis_id)]
        if abs(axis_value) < dead_zone:
            return 0
        return axis_value

    def axis_passed_threshold(self, axis_id: int, threshold: float = 0) -> bool:
        return self._axis_curr_frame[self.axis_key(axis_id)] > threshold

    def axis_tapped(self, axis_id: int) -> bool:
        tapped = self._tap_flag[self.axis_key(axis_id)]
        self._tap_flag[self.axis_key(axis_id)] = False
        return tapped

    def axis_toggle(self, axis_id: int, threshold: float = 0) -> bool:
        return (
            self._axis_curr_frame[self.axis_key(axis_id)] >= threshold
            and not self._axis_prev_frame[axis_id] >= threshold
        )

    def reset(self):
        self.joystick.quit()
        self.joystick = None
        self._num_buttons = None
        self._num_axes = None
        self._press_time.clear()
        self._tap_flag.clear()
        self._pressed_prev_frame.clear()
        self._pressed_curr_frame.clear()
        self._axis_prev_frame.clear()
        self._axis_curr_frame.clear()

    @property
    def num_buttons(self) -> int:
        if self._num_buttons is None and self.joystick is not None:
            self._num_buttons = self.joystick.get_numbuttons()
        return self._num_buttons

    @property
    def num_axes(self) -> int:
        if self._num_axes is None and self.joystick is not None:
            self._num_axes = self.joystick.get_numaxes()
        return self._num_axes

    @property
    def gamepad_identifier(self) -> GamepadIdentifier:
        if self.is_connected():
            try:
                return GamepadIdentifier(self.joystick.get_name())
            except ValueError:
                logger.warning(f"Unrecognized gamepad type: {self.joystick.get_name()}")
                # someone plugged in a rando controller, might as well try to use the bitdo mapping
                return GamepadIdentifier.BIT_DO_LITE_2

    @staticmethod
    def axis_key(axis_id: int) -> str:
        return f"axis{axis_id}"

    def update(self):
        if not self.joystick:
            logger.warning("joystick not initialized")
            return

        now = pygame.time.get_ticks()
        self._pressed_prev_frame = self._pressed_curr_frame.copy()
        self._axis_prev_frame = self._axis_curr_frame.copy()

        for button_id in range(self.num_buttons):
            pressed = bool(self.joystick.get_button(button_id))
            self._pressed_curr_frame[button_id] = pressed

            if pressed and not self._pressed_prev_frame[button_id]:
                self._press_time[button_id] = now

            if not pressed and self._pressed_prev_frame[button_id]:
                t0 = self._press_time.pop(button_id, None)
                if t0 is not None and now - t0 <= self.TAP_THRESHOLD_MS:
                    self._tap_flag[button_id] = True

        for axis_id in range(self.num_axes):
            axis_value = self.joystick.get_axis(axis_id)
            axis_key = self.axis_key(axis_id)

            self._axis_curr_frame[axis_key] = axis_value

            if self._axis_curr_frame[axis_key] and not self._axis_prev_frame[axis_key]:
                self._press_time[axis_key] = now

            if not self._axis_curr_frame[axis_key] and self._axis_prev_frame[axis_key]:
                t0 = self._press_time.pop(axis_key, None)
                if t0 is not None and now - t0 <= self.TAP_THRESHOLD_MS:
                    self._tap_flag[axis_key] = True

    @staticmethod
    def detect() -> Iterator["Gamepad"]:
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            return [Gamepad()]
        except pygame.error as e:
            print(f"Error initializing joystick module: {e}")
            return []

    def is_connected(self):
        return self.joystick is not None

    @staticmethod
    def gamepad_detected() -> bool:
        return pygame.joystick.get_count() > 0

    def run(self):
        # Give pygame and USB subsystems time to fully initialize
        time.sleep(1.5)
        while True:
            try:
                while Gamepad.gamepad_detected() and not self.is_connected():
                    try:
                        self.joystick = pygame.joystick.Joystick(0)
                        self.joystick.init()
                        print(f"{self.joystick.get_name()} connected")
                    except pygame.error as e:
                        print(f"Error connecting joystick: {e}")
                        # trying to touch joystick module from a thread becomes weird af
                        pygame.event.post(Event(REQUEST_JOYSTICK_MODULE_RESET))
                    except KeyboardInterrupt:
                        print("Program terminated")
                    except Exception:
                        pass

                if not Gamepad.gamepad_detected() and self.is_connected():
                    cached_name = self.joystick.get_name()
                    self.reset()
                    print(f"{cached_name} disconnected")
            except KeyboardInterrupt:
                print("Program terminated")
            except Exception:
                pass

            # check every 1 second for controller state
            time.sleep(1)
