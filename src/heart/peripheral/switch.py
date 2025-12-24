import json
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterator, Mapping, NoReturn, Self

import pygame
import reactivex
import serial
from bleak.backends.device import BLEDevice
from reactivex import create
from reactivex import operators as ops
from reactivex.abc import ObserverBase, SchedulerBase
from reactivex.disposable import Disposable

from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import (Input, InputDescriptor, Peripheral,
                                   PeripheralInfo, PeripheralMessageEnvelope,
                                   PeripheralTag)
from heart.peripheral.keyboard import (KeyboardAction, KeyboardEvent,
                                       KeyboardKey)
from heart.utilities.env import Configuration, get_device_ports
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import input_scheduler

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SwitchState:
    """Immutable snapshot of ``BaseSwitch`` state values."""

    rotational_value: int
    button_value: int
    long_button_value: int
    rotation_since_last_button_press: int
    rotation_since_last_long_button_press: int

class BaseSwitch(Peripheral[SwitchState]):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.rotational_value = 0

        self.button_value = 0
        self.rotation_value_at_last_button_press = self.rotational_value

        self.button_long_press_value = 0
        self.rotation_value_at_last_long_button_press = self.rotational_value

    def _event_stream(
        self
    ) -> reactivex.Observable[SwitchState]:
        return reactivex.interval(
            timedelta(milliseconds=10),
            scheduler=input_scheduler(),
        ).pipe(
            ops.map(lambda _: self._snapshot()),
            ops.distinct_until_changed(lambda x: x)
        )
        
    def _snapshot(self) -> SwitchState:
        return SwitchState(
            rotational_value=self.rotational_value,
            button_value=self.button_value,
            rotation_since_last_button_press=self.rotation_value_at_last_button_press,
            long_button_value=self.button_long_press_value,
            rotation_since_last_long_button_press=self.rotational_value - self.rotation_value_at_last_long_button_press,
        )

class FakeSwitch(BaseSwitch):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _key_press_stream(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        return KeyboardKey.get(key).observe.pipe(
            ops.map(PeripheralMessageEnvelope[KeyboardEvent].unwrap_peripheral),
            ops.filter(lambda event: event.action is KeyboardAction.PRESSED),
        )

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()
    
    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_switch",
            tags=[
                PeripheralTag(
                    name="input_variant",
                    variant="button",
                    metadata={"version": "v1"}
                ),
                # TODO: Allow the button to change its own tags in some cases
                PeripheralTag(
                    name="mode",
                    variant="main_rotary_button",
                ),
            ]
        )

    def inputs(
        self,
        *,
        event_bus: reactivex.Observable[Input] | None = None,
    ) -> tuple[InputDescriptor, ...]:
        keyboard_stream = reactivex.merge(
            self._key_press_stream(pygame.K_UP),
            self._key_press_stream(pygame.K_DOWN),
            self._key_press_stream(pygame.K_LEFT),
            self._key_press_stream(pygame.K_RIGHT),
        )
        return (
            InputDescriptor(
                name="keyboard.arrow_keys.pressed",
                stream=keyboard_stream,
                payload_type=KeyboardEvent,
                description=(
                    "Arrow key press events (KeyboardAction.PRESSED) mapped to "
                    "fake switch rotation and button increments."
                ),
            ),
        )

    def run(self) -> None:
        if not (Configuration.is_pi() and not Configuration.is_x11_forward()):
            def handle_key_up(_: Any) -> None:
                self.button_long_press_value += 1
                self.rotation_value_at_last_long_button_press = self.rotational_value
            
            def handle_key_down(_: Any) -> None:
                self.button_value += 1
                self.rotation_value_at_last_button_press = self.rotational_value

            def handle_key_left(_: Any) -> None:
                self.rotational_value -= 1

            def handle_key_right(_: Any) -> None:
                self.rotational_value += 1

            self._key_press_stream(pygame.K_UP).subscribe(on_next=handle_key_up)
            self._key_press_stream(pygame.K_DOWN).subscribe(on_next=handle_key_down)
            self._key_press_stream(pygame.K_LEFT).subscribe(on_next=handle_key_left)
            self._key_press_stream(pygame.K_RIGHT).subscribe(on_next=handle_key_right)
        else:
            logger.warning("Not running FakeSwitch")

    def _event_stream(
        self
    ) -> reactivex.Observable[SwitchState]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            return reactivex.empty()
        else:
            return reactivex.interval(
                timedelta(milliseconds=10),
                scheduler=input_scheduler(),
            ).pipe(
                ops.map(lambda _: self._snapshot()),
                ops.distinct_until_changed(lambda x: x)
            )

class Switch(BaseSwitch):
    def __init__(self, port: str, baudrate: int, *args: Any, **kwargs: Any) -> None:
        self.port = port
        self.baudrate = baudrate
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_Industries_LLC_Rotary_Trinkey_M0"):
            yield cls(port=port, baudrate=115200)

    def _connect_to_ser(self) -> Any:
        return serial.Serial(self.port, self.baudrate)

    def _read_from_switch(
        self,
        observer: ObserverBase[Any],
        scheduler: SchedulerBase | None,
    ) -> Disposable:
        while True:
            try:
                ser = self._connect_to_ser()
                try:
                    while True:
                        if ser.in_waiting > 0:
                            bus_data = ser.readline().decode("utf-8").rstrip()
                            data = json.loads(bus_data)
                            observer.on_next(data)
                except KeyboardInterrupt:
                    pass
                except Exception:
                    pass
                finally:
                    ser.close()
            except Exception:
                pass

            time.sleep(0.1)
        return Disposable()

    def run(self) -> None:
        source = create(self._read_from_switch)
        source.subscribe(
            on_next=self.update_due_to_data,
            scheduler=input_scheduler(),
        )

class BluetoothSwitch(BaseSwitch):
    def __init__(self, device: BLEDevice, *args: Any, **kwargs: Any) -> None:
        self.listener = UartListener(device=device)
        self.switches = [
            BaseSwitch() for index in range(4)
        ]
        self.connected = False
        super().__init__(*args, **kwargs)

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        raise NotImplementedError("Haven't figured out how to handle this multi-input case well.  Likely just map it to the observable(s)?")
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
        self.listener.start()

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
                try:
                    while True:
                        for event in self.listener.consume_events():
                            self.update_due_to_data(event)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    logger.info("Program terminated")
                except Exception:
                    self.connected = False
                    pass
                finally:
                    self.connected = False
                    self.listener.close()
            except Exception:
                self.connected = False
                number_of_retries_without_success += 1
                if number_of_retries_without_success > 5:
                    slow_poll = True

            time.sleep(30 if slow_poll else 5)
