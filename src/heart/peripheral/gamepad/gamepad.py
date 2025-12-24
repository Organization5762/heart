import subprocess
import time
from collections import defaultdict
from datetime import timedelta
from enum import Enum
from typing import Any, Iterator, Self

import pygame.joystick
import reactivex
from pygame.event import Event
from reactivex import operators as ops

from heart.peripheral.core import Peripheral, events
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import input_scheduler

logger = get_logger(__name__)


class GamepadIdentifier(Enum):
    # string values need to exactly match what's reported from joystick.get_name()
    # so check that first when adding a controller type
    BIT_DO_LITE_2 = "8BitDo Lite 2"
    SWITCH_PRO = "Nintendo Switch Pro Controller"

class Gamepad(Peripheral[Any]):
    EVENT_BUTTON = "gamepad.button"
    EVENT_AXIS = "gamepad.axis"
    EVENT_DPAD = "gamepad.dpad"
    EVENT_LIFECYCLE = "gamepad.lifecycle"

    def __init__(
        self, joystick_id: int = 0, joystick: pygame.joystick.JoystickType | None = None
    ) -> None:
        super().__init__()
        self.joystick_id = joystick_id
        self.joystick: pygame.joystick.JoystickType | None = joystick
        self.TAP_THRESHOLD_MS = 500

        self._num_buttons: int | None = None
        self._num_axes: int | None = None
        self._press_time: dict[int | str, int] = {}
        self._tap_flag: defaultdict[int | str, bool] = defaultdict(bool)
        self._pressed_prev_frame: defaultdict[int, bool] = defaultdict(bool)
        self._pressed_curr_frame: defaultdict[int, bool] = defaultdict(bool)
        self._axis_prev_frame: defaultdict[str, float] = defaultdict(float)
        self._axis_tapped_prev_frame: defaultdict[str, bool] = defaultdict(
            lambda: False
        )
        self._axis_curr_frame: defaultdict[str, float] = defaultdict(float)
        self._dpad_last_frame: tuple[float, float] = (0.0, 0.0)
        self._dpad_curr_frame: tuple[float, float] = (0.0, 0.0)

        self._last_lifecycle_status: str | None = None

    def is_held(self, button_id: int) -> bool:
        return self._pressed_curr_frame[button_id]

    def was_tapped(self, button_id: int) -> bool:
        tapped = self._tap_flag[button_id]
        self._tap_flag[button_id] = False
        return tapped

    def axis_value(self, axis_id: int, dead_zone: float = 0) -> float:
        axis_value = self._axis_curr_frame[self.axis_key(axis_id)]
        if abs(axis_value) < dead_zone:
            return 0
        return axis_value

    def axis_passed_threshold(self, axis_id: int, threshold: float = 0) -> bool:
        return self._axis_curr_frame[self.axis_key(axis_id)] > threshold

    def axis_tapped(self, axis_id: int, threshold: float = 0) -> bool:
        tapped = self._axis_curr_frame[self.axis_key(axis_id)] > threshold
        tapped_last_frame = self._axis_tapped_prev_frame[self.axis_key(axis_id)]
        self._axis_tapped_prev_frame[self.axis_key(axis_id)] = tapped
        return tapped and not tapped_last_frame

    def reset(self) -> None:
        if self.joystick is not None:
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
        return self._num_buttons or 0

    @property
    def num_axes(self) -> int:
        if self._num_axes is None and self.joystick is not None:
            self._num_axes = self.joystick.get_numaxes()
        return self._num_axes or 0

    @property
    def gamepad_identifier(self) -> GamepadIdentifier:
        if not self.is_connected() or self.joystick is None:
            raise RuntimeError("Attempted to read identifier of disconnected gamepad")
        try:
            return GamepadIdentifier(self.joystick.get_name())
        except ValueError:
            logger.warning("Unrecognized gamepad type: %s", self.joystick.get_name())
            # someone plugged in a rando controller, might as well try to use the bitdo mapping
            return GamepadIdentifier.BIT_DO_LITE_2

    @staticmethod
    def axis_key(axis_id: int) -> str:
        return f"axis{axis_id}"

    def update(self) -> None:
        try:
            self._update()
        except Exception as e:
            print(f"Error updating gamepad state: {e}")

    def _update(self) -> None:
        if not self.joystick:
            return

        # Refresh Pygame's internal event queue so that joystick state is up-to-date
        # Without this, axes may appear stuck at their previous values (often -1),
        # and button states may not change, leading to the behaviour where the
        # stick seems permanently pushed to the top-left and only some buttons
        # register. Calling pygame.event.pump() ensures Pygame processes any
        # pending input events before we query the current state.
        pygame.event.pump()

        now = pygame.time.get_ticks()
        self._pressed_prev_frame = self._pressed_curr_frame.copy()
        self._axis_prev_frame = self._axis_curr_frame.copy()
        self._dpad_last_frame = self._dpad_curr_frame

        self._dpad_curr_frame = self.joystick.get_hat(0)
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

    @classmethod
    def detect(cls) -> Iterator[Self]:
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            yield cls()
        except pygame.error as e:
            print(f"Error initializing joystick module: {e}")
            return

    def is_connected(self) -> bool:
        return self.joystick is not None

    @staticmethod
    def gamepad_detected() -> bool:
        return pygame.joystick.get_count() > 0

    def _read_from_gamepad(self, interval: int) -> None:
        try:
            while Gamepad.gamepad_detected() and not self.is_connected():
                try:
                    self.joystick = pygame.joystick.Joystick(0)
                    self.joystick.init()
                    logger.info(f"{self.joystick.get_name()} ready")
                except pygame.error as e:
                    logger.warning(f"Error connecting joystick: {e}")
                    # trying to touch joystick module from a thread becomes weird af
                    pygame.event.post(Event(events.REQUEST_JOYSTICK_MODULE_RESET))
                except Exception:
                    pass

            if not Gamepad.gamepad_detected() and self.is_connected():
                cached_name = self.joystick.get_name() if self.joystick else None
                self.reset()
                if cached_name is not None:
                    logger.info(f"{cached_name} disconnected")

            # Todo: We're reaching unfathomable levels of hard-coding.
            #  This will only work specifically with our pi4, and our 8bitdo
            #  controller. We only know the mac address bc we've explicitly
            #  paired the 8bitdo controller with the raspberry pi.
            #  God help us if it ever unpairs.
            if Configuration.is_pi():
                if not Gamepad.gamepad_detected():
                    result = subprocess.run(
                        ["bluetoothctl", "connect", "E4:17:D8:37:C3:40"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        logger.info("Successfully connected to 8bitdo controller")
                    else:
                        logger.warning("Failed to connect to 8bitdo controller")

        except KeyboardInterrupt:
            logger.info("Gamepad monitoring terminated")
        except Exception:
            logger.exception("Gamepad monitoring encountered an unexpected error")

    def run(self) -> None:
        # Give pygame and USB subsystems time to fully initialize.
        time.sleep(1.5)

        # check every 1 second for controller state, so that we can attempt to connect
        scheduler = input_scheduler()
        reactivex.interval(timedelta(seconds=1), scheduler=scheduler).subscribe(
            on_next=self._read_from_gamepad,
            scheduler=scheduler,
        )

        # Query the controller state frequently
        reactivex.interval(timedelta(milliseconds=20), scheduler=scheduler).pipe(
            ops.observe_on(scheduler),
        ).subscribe(on_next=lambda x: self._update())
