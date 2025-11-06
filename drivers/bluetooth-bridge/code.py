"""Bluetooth bridge firmware loop.

The original firmware was written with direct hardware calls that executed on
import.  That behaviour makes it impossible to exercise in CI because the
module immediately tries to talk to the board and blocks forever.  The driver
is now organised around a small runtime object so that unit tests can inject
test doubles for the BLE stack, LED and timing helpers.

When running on the microcontroller the ``main`` function still spins forever,
but the class based structure means CI can call :meth:`BluetoothBridgeRuntime.run_once`
with fake values and assert on the produced UART output without needing any of
the real hardware modules.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Iterable, Protocol

import board
import digitalio
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService


class SupportsWrite(Protocol):
    def write(self, data: bytes) -> None:  # pragma: no cover - typing protocol
        ...


class SupportsSleep(Protocol):
    def sleep(self, seconds: float) -> None:  # pragma: no cover - typing protocol
        ...


DELAY_BETWEEN_MESSAGES = 0.1
MINIMUM_LIGHT_ON_SECONDS = 0.05

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"


def _ensure_output_led() -> digitalio.DigitalInOut:
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    led.value = True
    return led


def gather_state() -> list[dict[str, str]]:
    """Collect state that should be streamed to the UART service."""

    gather_state.counter += 1
    return [{"event_type": "rotation", "data": gather_state.counter}]


gather_state.counter = 0


@dataclass
class BluetoothBridgeRuntime:
    """Coordinates BLE connectivity and UART writes."""

    ble: BLERadio
    uart: SupportsWrite
    advertisement: ProvideServicesAdvertisement
    led: digitalio.DigitalInOut
    gather_state: Callable[[], Iterable[dict[str, str]]]
    sleeper: SupportsSleep
    delay_seconds: float = DELAY_BETWEEN_MESSAGES
    not_connected_buffer: Deque[str] = field(default_factory=lambda: deque([], 10))
    _previous_message: str | None = None

    def _ensure_advertising(self) -> None:
        if not self.ble.advertising:
            self.ble.start_advertising(self.advertisement)

    def _encode_payload(self, payload: Iterable[dict[str, str]]) -> str:
        return json.dumps(list(payload)) + END_OF_MESSAGE_DELIMETER

    def _drain_buffer(self) -> None:
        while self.not_connected_buffer:
            self.uart.write(self.not_connected_buffer.popleft().encode(ENCODING))

    def run_once(self) -> None:
        """Execute a single iteration of the firmware loop."""

        self.led.value = True
        self._ensure_advertising()

        payload = self.gather_state()
        message = self._encode_payload(payload)

        if self.ble.connected:
            self._drain_buffer()
            if message != self._previous_message:
                self.uart.write(message.encode(ENCODING))
        else:
            if message != self._previous_message:
                self.not_connected_buffer.append(message)

        self._previous_message = message
        self.led.value = False
        self.sleeper.sleep(self.delay_seconds)


def create_runtime(
    *,
    ble: BLERadio | None = None,
    uart: SupportsWrite | None = None,
    advertisement: ProvideServicesAdvertisement | None = None,
    led: digitalio.DigitalInOut | None = None,
    gather_state_fn: Callable[[], Iterable[dict[str, str]]] = gather_state,
    sleeper: SupportsSleep | None = None,
    delay_seconds: float = DELAY_BETWEEN_MESSAGES,
) -> BluetoothBridgeRuntime:
    """Create a :class:`BluetoothBridgeRuntime` with real hardware components."""

    ble = ble or BLERadio()
    uart = uart or UARTService()
    advertisement = advertisement or ProvideServicesAdvertisement(uart)
    led = led or _ensure_output_led()

    if sleeper is None:
        import time

        sleeper = time

    return BluetoothBridgeRuntime(
        ble=ble,
        uart=uart,
        advertisement=advertisement,
        led=led,
        gather_state=gather_state_fn,
        sleeper=sleeper,
        delay_seconds=delay_seconds,
    )


def main(runtime: BluetoothBridgeRuntime | None = None) -> None:
    """Run the firmware loop until interrupted."""

    runtime = runtime or create_runtime()

    while True:
        runtime.run_once()


if __name__ == "__main__":  # pragma: no cover - exercised on hardware
    main()
