import json
import time
from dataclasses import replace
from typing import Any, Iterator, Mapping, NoReturn, Self

import serial
from bleak.backends.device import BLEDevice

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         SWITCH_ROTATION)
from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.event_bus import EventBus
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseSwitch(Peripheral):
    EVENT_LIFECYCLE = "switch.lifecycle"

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
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

        if event_bus is not None:
            self.attach_event_bus(event_bus)

    def run(self) -> None:
        return

    def attach_event_bus(self, event_bus: EventBus) -> None:
        super().attach_event_bus(event_bus)
        self._mark_connected()

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
        self.emit_input(event)

    def _emit_lifecycle(self, status: str, *, extra: Mapping[str, Any] | None = None) -> None:
        if self._last_lifecycle_status == status:
            return

        payload: dict[str, Any] = {"status": status}
        if extra:
            payload.update(extra)

        event = Input(
            event_type=self.EVENT_LIFECYCLE,
            data=payload,
            producer_id=self._default_producer_id,
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

    def attach_event_bus(self, event_bus: EventBus) -> None:
        super().attach_event_bus(event_bus)
        for switch in self.switches:
            switch.attach_event_bus(event_bus)

    def update_due_to_data(self, data: dict[str, int]) -> None:
        producer_id = data.get("producer_id", 0)
        self.switches[producer_id].update_due_to_data(data)

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
