import subprocess
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import timedelta
from enum import StrEnum
from typing import Any, Iterator, Self

import pygame.joystick
from manyfold import (DetectionNode, Layer, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, Timer, TypedRoute, Variant,
                      route)
from manyfold.sensor_io import SensorEvent, sensor_event_schema
from pygame.event import Event

from heart.peripheral.core import (Peripheral, PeripheralInfo, PeripheralTag,
                                   events)
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
INITIALIZATION_DELAY_SECONDS = 1.5
DEFAULT_JOYSTICK_ID = 0
DEFAULT_AXIS_DEAD_ZONE = 0.0
DEFAULT_AXIS_THRESHOLD = 0.0
RAW_LOG_AXIS_THRESHOLD = 0.05
JOYSTICK_EVENT_TYPES = (
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONUP,
    pygame.JOYBUTTONDOWN,
    pygame.JOYDEVICEADDED,
    pygame.JOYDEVICEREMOVED,
)
DEFAULT_BLUETOOTH_GAMEPAD_MACS = (
    "E4:17:D8:37:C3:40",
    "E4:17:D8:37:FE:88",
    "E4:17:D8:E9:76:C8",
    "E4:17:D8:E9:99:B3",
)
BLUETOOTH_RECONNECT_INTERVAL_SECONDS = 30.0
BLUETOOTH_CONNECT_TIMEOUT_SECONDS = 1.0
GAMEPAD_GRAPH_OWNER = OwnerName("heart.gamepad")
GAMEPAD_GRAPH_FAMILY = StreamFamily("peripheral")


def gamepad_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=GAMEPAD_GRAPH_OWNER,
        family=GAMEPAD_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartGamepadDetectionEvent"),
    )


def gamepad_exception_schema() -> Schema[BaseException]:
    def encode(exc: BaseException) -> bytes:
        return f"{type(exc).__name__}:{exc}".encode("utf-8")

    def decode(payload: bytes) -> BaseException:
        return RuntimeError(payload.decode("utf-8"))

    return Schema(
        schema_id="PythonException",
        version=1,
        encode=encode,
        decode=decode,
    )


def gamepad_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=GAMEPAD_GRAPH_OWNER,
        family=GAMEPAD_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=gamepad_exception_schema(),
    )


class GamepadIdentifier(StrEnum):
    # string values need to exactly match what's reported from joystick.get_name()
    # so check that first when adding a controller type
    BIT_DO_LITE_2 = "8BitDo Lite 2"
    SWITCH_PRO = "Nintendo Switch Pro Controller"
    SWITCH_PRO_SHORT = "Pro Controller"


class Gamepad(Peripheral[Any]):
    EVENT_BUTTON = "gamepad.button"
    EVENT_AXIS = "gamepad.axis"
    EVENT_DPAD = "gamepad.dpad"
    EVENT_LIFECYCLE = "gamepad.lifecycle"

    def __init__(
        self,
        joystick_id: int = DEFAULT_JOYSTICK_ID,
        joystick: pygame.joystick.JoystickType | None = None,
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
        self._last_bluetooth_connect_attempt: float | None = None
        self._last_logged_raw_state: tuple[
            tuple[int, ...], tuple[tuple[str, float], ...], tuple[float, float]
        ] | None = None

    def is_held(self, button_id: int) -> bool:
        return self._pressed_curr_frame[button_id]

    def was_tapped(self, button_id: int) -> bool:
        tapped = self._tap_flag[button_id]
        self._tap_flag[button_id] = False
        return tapped

    def axis_value(
        self, axis_id: int, dead_zone: float = DEFAULT_AXIS_DEAD_ZONE
    ) -> float:
        axis_value = self._axis_curr_frame[self.axis_key(axis_id)]
        if abs(axis_value) < dead_zone:
            return 0
        return axis_value

    def axis_passed_threshold(
        self, axis_id: int, threshold: float = DEFAULT_AXIS_THRESHOLD
    ) -> bool:
        return self._axis_curr_frame[self.axis_key(axis_id)] > threshold

    def axis_tapped(
        self, axis_id: int, threshold: float = DEFAULT_AXIS_THRESHOLD
    ) -> bool:
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
        except Exception:
            logger.exception("Error updating gamepad state")

    def _update(self) -> None:
        if not self.joystick:
            return

        self._log_pygame_joystick_events()

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

        try:
            self._dpad_curr_frame = self.joystick.get_hat(0)
        except pygame.error:
            pass

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

        active_buttons = tuple(
            button_id
            for button_id in range(self.num_buttons)
            if self._pressed_curr_frame[button_id]
        )
        active_axes = tuple(
            sorted(
                (
                    axis_key,
                    round(axis_value, 2),
                )
                for axis_key, axis_value in self._axis_curr_frame.items()
                if abs(axis_value) >= RAW_LOG_AXIS_THRESHOLD
            )
        )
        raw_state = (active_buttons, active_axes, self._dpad_curr_frame)
        if raw_state != self._last_logged_raw_state:
            self._last_logged_raw_state = raw_state
            logger.info(
                "Gamepad raw state name=%s buttons=%s axes=%s hat=%s",
                self.joystick.get_name(),
                active_buttons,
                active_axes,
                self._dpad_curr_frame,
            )

    def _log_pygame_joystick_events(self) -> None:
        for event in pygame.event.get(JOYSTICK_EVENT_TYPES):
            logger.info(
                "Gamepad pygame event type=%s attrs=%s",
                pygame.event.event_name(event.type),
                {
                    key: value
                    for key, value in event.__dict__.items()
                    if key != "type"
                },
            )

    @classmethod
    def detect(cls) -> Iterator[Self]:
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            yield cls()
        except pygame.error:
            logger.exception("Error initializing joystick module")
            return

    @classmethod
    def detection_node(
        cls,
        *,
        detector: Callable[[], Iterable["Gamepad"]] | None = None,
        output_route: TypedRoute[SensorEvent] | None = None,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or gamepad_detection_route()

        def mapper(peripheral: "Gamepad") -> SensorEvent:
            joystick_name = None
            if peripheral.joystick is not None:
                joystick_name = peripheral.joystick.get_name()
            return SensorEvent(
                event_type="peripheral.gamepad.detected",
                data={
                    "joystick_id": peripheral.joystick_id,
                    "connected": peripheral.is_connected(),
                    "name": joystick_name,
                },
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        return DetectionNode(
            name="heart-gamepad-detection",
            detector=detector or cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            error_route=gamepad_error_route(),
            group="gamepad-detection",
            start_immediately=start_immediately,
        )

    def peripheral_info(self) -> PeripheralInfo:
        tags = [
            PeripheralTag(name="input_variant", variant="gamepad"),
        ]
        if self.joystick is not None:
            tags.append(
                PeripheralTag(name="gamepad_name", variant=self.joystick.get_name())
            )
        return PeripheralInfo(
            id=f"gamepad:{self.joystick_id}",
            tags=tags,
        )

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

            if Configuration.is_pi() and not Gamepad.gamepad_detected():
                self._connect_bluetooth_gamepads()

        except KeyboardInterrupt:
            logger.info("Program terminated")
        except Exception:
            logger.debug("Unexpected error while reading gamepad state", exc_info=True)

    def _connect_bluetooth_gamepads(self) -> None:
        now = time.monotonic()
        if (
            self._last_bluetooth_connect_attempt is not None
            and now - self._last_bluetooth_connect_attempt
            < BLUETOOTH_RECONNECT_INTERVAL_SECONDS
        ):
            return
        self._last_bluetooth_connect_attempt = now

        for mac_address in DEFAULT_BLUETOOTH_GAMEPAD_MACS:
            command = self._bluetooth_connect_command(mac_address)
            if command is None:
                return
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=BLUETOOTH_CONNECT_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Timed out connecting to bluetooth gamepad %s",
                    mac_address,
                )
                continue
            if result.returncode == 0:
                logger.info(
                    "Requested connection to bluetooth gamepad %s",
                    mac_address,
                )
            else:
                logger.warning(
                    "Failed to connect to bluetooth gamepad %s: %s",
                    mac_address,
                    (result.stderr or result.stdout).strip(),
                )

    @staticmethod
    def _bluetooth_connect_command(mac_address: str) -> list[str] | None:
        if shutil.which("bluetoothctl"):
            return ["bluetoothctl", "connect", mac_address]
        if shutil.which("blueutil"):
            return ["blueutil", "--connect", mac_address]
        return None

    def run(self) -> None:
        # Give pygame and USB subsystems time to fully initialize
        # TODO: Is this needed?
        time.sleep(INITIALIZATION_DELAY_SECONDS)

        # macOS AppKit requires SDL event and joystick APIs to run on the process
        # main thread, so route both polling loops through the frame-thread queue.
        Timer(period=timedelta(seconds=1)).then_on_main_thread().subscribe(
            on_next=self._read_from_gamepad,
        )

        Timer(period=timedelta(milliseconds=20)).then_on_main_thread().subscribe(
            on_next=lambda _: self._update()
        )
