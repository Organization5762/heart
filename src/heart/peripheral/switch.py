import json
import threading
import time
from dataclasses import dataclass, replace
from datetime import timedelta
from functools import cached_property
from typing import Any, Callable, Iterator, Mapping, NoReturn, Self

import reactivex
import serial
from bleak.backends.device import BLEDevice
from reactivex import operators as ops

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         SWITCH_ROTATION)
from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import Input, Peripheral
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SwitchState:
    """Immutable snapshot of ``BaseSwitch`` state values."""

    rotational_value: int
    button_value: int
    long_button_value: int
    rotation_since_last_button_press: int
    rotation_since_last_long_button_press: int


class BaseSwitch(Peripheral):
    EVENT_LIFECYCLE = "switch.lifecycle"

    def __init__(
        self,
        *,
        producer_id: int | None = None,
    ) -> None:
        super().__init__()
        self.rotational_value = 0

        self.button_value = 0
        self.rotation_value_at_last_button_press = self.rotational_value

        self.button_long_press_value = 0
        self.rotation_value_at_last_long_button_press = self.rotational_value

        self._default_producer_id = producer_id if producer_id is not None else 0
        self._has_explicit_producer = producer_id is not None
        self._last_lifecycle_status: str | None = None
        self._state_callbacks: list[Callable[[SwitchState], None]] = []
        self._state_lock = threading.RLock()

    def run(self) -> None:
        return

    def get_rotation_since_last_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_button_press

    def get_rotation_since_last_long_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_long_button_press

    def get_rotational_value(self) -> int:
        return self.rotational_value

    def get_button_value(self) -> int:
        return self.button_value

    def get_long_button_value(self) -> int:
        return self.button_long_press_value

    def get_state(self) -> SwitchState:
        """Return the latest switch state snapshot."""

        with self._state_lock:
            return self._snapshot()

    def subscribe_state(
        self, callback: Callable[[SwitchState], None], *, replay: bool = True
    ) -> Callable[[], None]:
        """Register ``callback`` for state updates.

        Parameters
        ----------
        callback:
            Callable invoked whenever the switch state changes.
        replay:
            Emit the current state to the callback immediately after
            subscription.  Defaults to ``True``.

        Returns
        -------
        Callable[[], None]
            Function that removes ``callback`` from future notifications.
        """

        with self._state_lock:
            self._state_callbacks.append(callback)
            snapshot = self._snapshot()

        if replay:
            callback(snapshot)

        def _unsubscribe() -> None:
            with self._state_lock:
                try:
                    self._state_callbacks.remove(callback)
                except ValueError:
                    return

        return _unsubscribe

    @cached_property
    def observe(
        self
    ) -> reactivex.Observable[SwitchState]:
        return reactivex.interval(timedelta(milliseconds=10)).pipe(
            ops.map(lambda _: self._snapshot()),
            ops.distinct_until_changed(lambda x: x)
        )
        

    def handle_input(self, data: Input) -> None:
        event = self._normalize_event(data)
        if event is None:
            return

        if event.event_type == BUTTON_PRESS:
            self.button_value += int(event.data)
            # Button was pressed, update last_rotational_value
            self.rotation_value_at_last_button_press = self.rotational_value

        if event.event_type == BUTTON_LONG_PRESS:
            self.button_long_press_value += int(event.data)
            # Button was pressed, update last_rotational_value
            self.rotation_value_at_last_long_button_press = self.rotational_value

        if event.event_type == SWITCH_ROTATION:
            self.rotational_value = int(event.data)

        self._publish_event(event)
        self._notify_state_changed()

    # ------------------------------------------------------------------
    # Event bus helpers
    # ------------------------------------------------------------------
    def _normalize_event(self, data: Input) -> Input | None:
        if data.event_type not in {BUTTON_PRESS, BUTTON_LONG_PRESS, SWITCH_ROTATION}:
            logger.debug("Ignoring unknown switch event type: %s", data.event_type)
            return None

        if data.event_type == SWITCH_ROTATION:
            value = int(data.data)
        else:
            value = int(data.data)

        producer_id = self._resolve_producer_id(data)
        return replace(data, data=value, producer_id=producer_id)

    def _resolve_producer_id(self, data: Input) -> int:
        if self._has_explicit_producer:
            return self._default_producer_id
        self._default_producer_id = data.producer_id
        return data.producer_id

    def _publish_event(self, event: Input) -> None:
        raise NotImplementedError("")

    def _snapshot(self) -> SwitchState:
        return SwitchState(
            rotational_value=self.rotational_value,
            button_value=self.button_value,
            long_button_value=self.button_long_press_value,
            rotation_since_last_button_press=self.get_rotation_since_last_button_press(),
            rotation_since_last_long_button_press=self.get_rotation_since_last_long_button_press(),
        )

    def _notify_state_changed(self) -> None:
        with self._state_lock:
            callbacks = tuple(self._state_callbacks)
            snapshot = self._snapshot()

        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:
                logger.exception("Switch state callback failed", exc_info=True)

    def _emit_lifecycle(self, status: str, *, extra: Mapping[str, Any] | None = None) -> None:
        if self._last_lifecycle_status == status:
            return

        payload: dict[str, Any] = {"status": status}
        if extra:
            payload.update(extra)

        # event = Input(
        #     event_type=self.EVENT_LIFECYCLE,
        #     data=payload,
        #     producer_id=self._default_producer_id,
        # )
        raise NotImplementedError("")
        self._last_lifecycle_status = status

    def _mark_connected(self) -> None:
        if self._last_lifecycle_status is None:
            self._emit_lifecycle("connected")
        elif self._last_lifecycle_status == "suspected_disconnect":
            self._emit_lifecycle("recovered")

    def _mark_disconnect(self, *, suspected: bool) -> None:
        status = "suspected_disconnect" if suspected else "disconnected"
        self._emit_lifecycle(status)


class FakeSwitch(BaseSwitch):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def run(self) -> None:
        return


class Switch(BaseSwitch):
    def __init__(self, port: str, baudrate: int, *args, **kwargs) -> None:
        self.port = port
        self.baudrate = baudrate
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_Industries_LLC_Rotary_Trinkey_M0"):
            yield cls(port=port, baudrate=115200)

    def _connect_to_ser(self):
        return serial.Serial(self.port, self.baudrate)

    def run(self) -> NoReturn:
        # If it crashes, try to re-connect
        while True:
            try:
                ser = self._connect_to_ser()
                self._mark_connected()
                try:
                    while True:
                        if ser.in_waiting > 0:
                            bus_data = ser.readline().decode("utf-8").rstrip()
                            data = json.loads(bus_data)
                            self.update_due_to_data(data)
                except KeyboardInterrupt:
                    self._mark_disconnect(suspected=False)
                    print("Program terminated")
                except Exception:
                    self._mark_disconnect(suspected=True)
                    pass
                finally:
                    ser.close()
            except Exception:
                self._mark_disconnect(suspected=True)

            time.sleep(0.1)


class BluetoothSwitch(BaseSwitch):
    def __init__(self, device: BLEDevice, *args, **kwargs) -> None:
        self.listener = UartListener(device=device)
        self.switches = [
            BaseSwitch(producer_id=index) for index in range(4)
        ]
        self.connected = False
        super().__init__(*args, **kwargs)

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        producer_raw = data.get("producer_id", 0)
        try:
            producer_id = int(producer_raw)
        except (TypeError, ValueError):
            producer_id = 0

        if not 0 <= producer_id < len(self.switches):
            logger.debug("Ignoring switch payload with invalid producer: %s", data)
            return

        payload = dict(data)
        payload["producer_id"] = producer_id
        self.switches[producer_id].update_due_to_data(payload)

        # Update first producer as if it is the main switch
        if producer_id == 0:
            main_switch = self.switches[0]
            self.rotational_value = main_switch.rotational_value

            self.button_value = main_switch.button_value
            self.rotation_value_at_last_button_press = (
                main_switch.rotation_value_at_last_button_press
            )

            self.button_long_press_value = main_switch.button_long_press_value
            self.rotation_value_at_last_long_button_press = (
                main_switch.rotation_value_at_last_long_button_press
            )

    def switch_zero(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[0]

    def switch_one(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[1]

    def switch_two(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[2]

    def switch_three(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[3]

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for device in UartListener._discover_devices():
            yield cls(device=device)

    def _connect_to_ser(self) -> None:
        return self.listener.start()

    def run(self) -> NoReturn:
        slow_poll = False
        number_of_retries_without_success = 0
        # If it crashes, try to re-connect
        while True:
            try:
                self._connect_to_ser()
                number_of_retries_without_success = 0
                slow_poll = False
                self.connected = True
                self._mark_connected()
                try:
                    while True:
                        for event in self.listener.consume_events():
                            self.update_due_to_data(event)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    self._mark_disconnect(suspected=False)
                    print("Program terminated")
                except Exception:
                    self.connected = False
                    self._mark_disconnect(suspected=True)
                    pass
                finally:
                    self.connected = False
                    self.listener.close()
            except Exception:
                self.connected = False
                number_of_retries_without_success += 1
                self._mark_disconnect(suspected=True)
                if number_of_retries_without_success > 5:
                    slow_poll = True

            time.sleep(30 if slow_poll else 5)
