import math
import subprocess
import time
from collections import defaultdict
from enum import Enum
from typing import Iterator, NoReturn, Self

import pygame.joystick
from pygame.event import Event

from heart.peripheral.core import Input, Peripheral, events
from heart.peripheral.core.event_bus import EventBus
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class GamepadIdentifier(Enum):
    # string values need to exactly match what's reported from joystick.get_name()
    # so check that first when adding a controller type
    BIT_DO_LITE_2 = "8BitDo Lite 2"
    SWITCH_PRO = "Nintendo Switch Pro Controller"


class Gamepad(Peripheral):
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
        self._dpad_last_frame: tuple[int, int] = (0, 0)
        self._dpad_curr_frame: tuple[int, int] = (0, 0)

        self._last_lifecycle_status: str | None = None

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

    def axis_tapped(self, axis_id: int, threshold: float = 0) -> bool:
        tapped = self._axis_curr_frame[self.axis_key(axis_id)] > threshold
        tapped_last_frame = self._axis_tapped_prev_frame[self.axis_key(axis_id)]
        self._axis_tapped_prev_frame[self.axis_key(axis_id)] = tapped
        return tapped and not tapped_last_frame

    def get_dpad_value(self) -> tuple[int, int]:
        return self._dpad_curr_frame

    def reset(self):
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
        self._mark_disconnect(suspected=False)

    def attach_event_bus(self, event_bus: EventBus) -> None:
        super().attach_event_bus(event_bus)
        if self.is_connected():
            self._mark_connected()

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
        if self.joystick is None:
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
        self._emit_dpad_if_changed()
        for button_id in range(self.num_buttons):
            pressed = bool(self.joystick.get_button(button_id))
            self._pressed_curr_frame[button_id] = pressed

            if pressed and not self._pressed_prev_frame[button_id]:
                self._press_time[button_id] = now

            if not pressed and self._pressed_prev_frame[button_id]:
                t0 = self._press_time.pop(button_id, None)
                if t0 is not None and now - t0 <= self.TAP_THRESHOLD_MS:
                    self._tap_flag[button_id] = True

            if pressed != self._pressed_prev_frame[button_id]:
                self._emit_button_event(button_id, pressed)

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

            if not math.isclose(
                self._axis_curr_frame[axis_key],
                self._axis_prev_frame[axis_key],
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                self._emit_axis_event(axis_id, self._axis_curr_frame[axis_key])

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

    def run(self) -> NoReturn:
        # Give pygame and USB subsystems time to fully initialize
        time.sleep(1.5)
        while True:
            try:
                while Gamepad.gamepad_detected() and not self.is_connected():
                    try:
                        self.joystick = pygame.joystick.Joystick(0)
                        self.joystick.init()
                        self._mark_connected()
                        print(f"{self.joystick.get_name()} ready")
                    except pygame.error as e:
                        print(f"Error connecting joystick: {e}")
                        # trying to touch joystick module from a thread becomes weird af
                        pygame.event.post(Event(events.REQUEST_JOYSTICK_MODULE_RESET))
                    except KeyboardInterrupt:
                        print("Program terminated")
                    except Exception:
                        pass

                if not Gamepad.gamepad_detected() and self.is_connected():
                    cached_name = self.joystick.get_name() if self.joystick else None
                    self._mark_disconnect(suspected=True)
                    self.reset()
                    if cached_name is not None:
                        print(f"{cached_name} disconnected")

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
                            print("Successfully connected to 8bitdo controller")
                        else:
                            print("Failed to connect to 8bitdo controller")

            except KeyboardInterrupt:
                print("Program terminated")
            except Exception:
                pass

            # check every 1 second for controller state
            time.sleep(1)

    # ------------------------------------------------------------------
    # Event bus helpers
    # ------------------------------------------------------------------
    def _emit_button_event(self, button_id: int, pressed: bool) -> None:
        event = Input(
            event_type=self.EVENT_BUTTON,
            data={"button": button_id, "pressed": pressed},
            producer_id=self.joystick_id,
        )
        self.emit_input(event)

    def _emit_axis_event(self, axis_id: int, value: float) -> None:
        event = Input(
            event_type=self.EVENT_AXIS,
            data={"axis": axis_id, "value": float(value)},
            producer_id=self.joystick_id,
        )
        self.emit_input(event)

    def _emit_dpad_if_changed(self) -> None:
        if self._dpad_curr_frame == self._dpad_last_frame:
            return
        event = Input(
            event_type=self.EVENT_DPAD,
            data={"x": self._dpad_curr_frame[0], "y": self._dpad_curr_frame[1]},
            producer_id=self.joystick_id,
        )
        self.emit_input(event)

    def _emit_lifecycle(self, status: str) -> None:
        if self._last_lifecycle_status == status:
            return
        event = Input(
            event_type=self.EVENT_LIFECYCLE,
            data={"status": status},
            producer_id=self.joystick_id,
        )
        self.emit_input(event)
        self._last_lifecycle_status = status

    def _mark_connected(self) -> None:
        if self._last_lifecycle_status is None:
            self._emit_lifecycle("connected")
        elif self._last_lifecycle_status == "suspected_disconnect":
            self._emit_lifecycle("recovered")

    def _mark_disconnect(self, *, suspected: bool) -> None:
        status = "suspected_disconnect" if suspected else "disconnected"
        self._emit_lifecycle(status)
