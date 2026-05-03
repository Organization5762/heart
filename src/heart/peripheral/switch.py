import asyncio
import json
import time
from dataclasses import dataclass
from datetime import timedelta
from threading import Thread
from typing import Any, Iterator, Mapping, NoReturn, Self

import reactivex
import serial
from bleak.backends.device import BLEDevice
from reactivex import create
from reactivex import operators as ops
from reactivex.abc import ObserverBase, SchedulerBase
from reactivex.disposable import Disposable

from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import (Peripheral, PeripheralInfo,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.keyboard import (KeyboardEvent, KeyboardKey,
                                       KeyPressedEvent)
from heart.utilities.env import Configuration, get_device_ports
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import (blocking_io_scheduler,
                                               interval_in_background,
                                               pipe_in_background)

logger = get_logger(__name__)
SERIAL_RECONNECT_DELAY_SECONDS = 0.1
BLUETOOTH_EVENT_POLL_DELAY_SECONDS = 0.1
BLUETOOTH_RETRY_DELAY_SECONDS = 5
BLUETOOTH_SLOW_RETRY_DELAY_SECONDS = 30
BLUETOOTH_MAX_RETRY_ATTEMPTS = 5
BLUETOOTH_SWITCH_THREAD_NAME = "peripheral-bluetooth-switch"


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
        return pipe_in_background(
            interval_in_background(period=timedelta(milliseconds=10)),
            ops.map(lambda _: self._snapshot()),
            ops.distinct_until_changed(lambda x: x)
        )

    def _snapshot(self) -> SwitchState:
        result = SwitchState(
            rotational_value=self.rotational_value,
            button_value=self.button_value,
            rotation_since_last_button_press=self.rotational_value - self.rotation_value_at_last_button_press,
            long_button_value=self.button_long_press_value,
            rotation_since_last_long_button_press=self.rotational_value - self.rotation_value_at_last_long_button_press,
        )
        return result

    def get_rotation_since_last_long_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_long_button_press

class FakeSwitch(BaseSwitch):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._navigation_subscription = None

    def _key_press_stream(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        def _unwrap(envelope: PeripheralMessageEnvelope[KeyboardEvent]) -> KeyboardEvent:
            return envelope.data

        def _is_pressed(event: KeyboardEvent) -> bool:
            return isinstance(event, KeyPressedEvent)

        result = pipe_in_background(
            KeyboardKey.get(key).observe,
            ops.map(_unwrap),
            ops.filter(_is_pressed),
        )
        return result

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

    def run(self) -> None:
        if (
            Configuration.use_mock_switch()
            or not (Configuration.is_pi() and not Configuration.is_x11_forward())
        ):
            from heart.runtime.game_loop import GameLoop

            loop = GameLoop.get_game_loop()
            if loop is None:
                logger.warning("FakeSwitch requires an active GameLoop for navigation input")
                return

            navigation = loop.peripheral_manager.navigation_profile
            self._navigation_subscription = navigation.subscribe_events(
                on_browse_delta=self._handle_browse,
                on_activate=self._handle_activate,
                on_alternate_activate=self._handle_alternate_activate,
            )
        else:
            logger.warning("Not running FakeSwitch")

    def _handle_alternate_activate(self, _: Any) -> None:
        self.button_long_press_value += 1
        self.rotation_value_at_last_long_button_press = self.rotational_value

    def _handle_activate(self, _: Any) -> None:
        self.button_value += 1
        self.rotation_value_at_last_button_press = self.rotational_value

    def _handle_browse(self, delta: int) -> None:
        self.rotational_value += delta

    def _event_stream(
        self
    ) -> reactivex.Observable[SwitchState]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            return reactivex.empty()
        else:
            result = pipe_in_background(
                interval_in_background(period=timedelta(milliseconds=10)),
                ops.map(lambda _: self._snapshot()),
                ops.distinct_until_changed(lambda x: x),
            )
            return result

class Switch(BaseSwitch):
    def __init__(self, port: str, baudrate: int, *args: Any, **kwargs: Any) -> None:
        self.port = port
        self.baudrate = baudrate
        self._subscription = None
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

            time.sleep(SERIAL_RECONNECT_DELAY_SECONDS)
        return Disposable()

    def run(self) -> None:
        source = create(self._read_from_switch).pipe(
            ops.subscribe_on(blocking_io_scheduler()),
        )
        self._subscription = source.subscribe(
            on_next=self.update_due_to_data,
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
        devices = asyncio.run(UartListener._discover_devices())
        for device in devices:
            yield cls(device=device)

    def _connect_to_ser(self) -> None:
        self.listener.start()

    def run(self) -> None:
        Thread(
            name=BLUETOOTH_SWITCH_THREAD_NAME,
            target=self._run_listener_loop,
            daemon=True,
        ).start()

    def _run_listener_loop(self) -> NoReturn:
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
                        time.sleep(BLUETOOTH_EVENT_POLL_DELAY_SECONDS)
                except KeyboardInterrupt:
                    logger.info("Program terminated")
                except Exception:
                    self.connected = False
                    logger.exception("Bluetooth switch listener failed; reconnecting.")
                finally:
                    self.connected = False
                    self.listener.close()
            except Exception:
                self.connected = False
                number_of_retries_without_success += 1
                if number_of_retries_without_success > BLUETOOTH_MAX_RETRY_ATTEMPTS:
                    slow_poll = True
                logger.exception(
                    "Failed to connect to Bluetooth switch; retrying (%s/%s).",
                    number_of_retries_without_success,
                    BLUETOOTH_MAX_RETRY_ATTEMPTS,
                )

            time.sleep(
                BLUETOOTH_SLOW_RETRY_DELAY_SECONDS
                if slow_poll
                else BLUETOOTH_RETRY_DELAY_SECONDS
            )
