import json
from collections import deque

import driver_loader
import pytest


class FakeDigitalInOut:
    def __init__(self, pin):
        self.pin = pin
        self.direction = None
        self.pull = None
        self.value = False


class FakeDirection:
    OUTPUT = "output"


class FakePull:
    UP = "up"
    DOWN = "down"


class FakeBLE:
    advertising = False
    connected = False

    def start_advertising(self, _):
        self.advertising = True


class FakeAdvertisement:
    def __init__(self, *_args, **_kwargs):
        pass


class FakeUARTService:
    def __init__(self):
        pass


advertising_standard = driver_loader.make_module(
    "adafruit_ble.advertising.standard", ProvideServicesAdvertisement=FakeAdvertisement
)
advertising_module = driver_loader.make_module(
    "adafruit_ble.advertising", standard=advertising_standard
)
services_nordic = driver_loader.make_module(
    "adafruit_ble.services.nordic", UARTService=FakeUARTService
)
services_module = driver_loader.make_module(
    "adafruit_ble.services", nordic=services_nordic
)

STUBS = {
    "board": driver_loader.make_module("board", LED="led"),
    "digitalio": driver_loader.make_module(
        "digitalio", DigitalInOut=FakeDigitalInOut, Direction=FakeDirection, Pull=FakePull
    ),
    "adafruit_ble": driver_loader.make_module(
        "adafruit_ble",
        BLERadio=FakeBLE,
        advertising=advertising_module,
        services=services_module,
    ),
    "adafruit_ble.advertising": advertising_module,
    "adafruit_ble.advertising.standard": advertising_standard,
    "adafruit_ble.services": services_module,
    "adafruit_ble.services.nordic": services_nordic,
}

bluetooth_bridge = driver_loader.load_driver_module("bluetooth-bridge", stubs=STUBS)
BluetoothBridgeRuntime = bluetooth_bridge.BluetoothBridgeRuntime
END_OF_MESSAGE_DELIMETER = bluetooth_bridge.END_OF_MESSAGE_DELIMETER
ENCODING = bluetooth_bridge.ENCODING


class StubBLE:
    def __init__(self):
        self.connected = False
        self.advertising = False
        self.start_calls = []

    def start_advertising(self, advertisement):
        self.advertising = True
        self.start_calls.append(advertisement)


class StubUART:
    def __init__(self):
        self.writes = []

    def write(self, payload: bytes) -> None:
        self.writes.append(payload)


class StubLED:
    def __init__(self):
        self.value = False


class StubSleeper:
    def __init__(self):
        self.calls = []

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture()
def runtime_factory():
    def _factory(payloads):
        sequence = list(payloads)
        index = {"value": 0}

        def gather_state():
            if index["value"] < len(sequence):
                result = sequence[index["value"]]
                index["value"] += 1
            else:
                result = sequence[-1]
            return result

        ble = StubBLE()
        uart = StubUART()
        led = StubLED()
        sleeper = StubSleeper()
        runtime = BluetoothBridgeRuntime(
            ble=ble,
            uart=uart,
            advertisement=object(),
            led=led,
            gather_state=gather_state,
            sleeper=sleeper,
            delay_seconds=0,
            not_connected_buffer=deque([], 5),
        )
        return runtime, ble, uart, led, sleeper

    return _factory


def _decode_payload(payload_bytes: bytes):
    payload_str = payload_bytes.decode(ENCODING)
    assert payload_str.endswith(END_OF_MESSAGE_DELIMETER)
    return json.loads(payload_str[:-1])


def test_runtime_buffers_and_flushes_messages(runtime_factory):
    runtime, ble, uart, led, sleeper = runtime_factory(
        [
            [{"event_type": "rotation", "data": 1}],
            [{"event_type": "rotation", "data": 2}],
            [{"event_type": "rotation", "data": 2}],
        ]
    )

    runtime.run_once()
    assert ble.advertising is True
    assert ble.start_calls
    assert led.value is False
    assert runtime.not_connected_buffer
    assert uart.writes == []

    ble.connected = True
    runtime.run_once()
    assert runtime.not_connected_buffer == deque([], 5)
    assert [_decode_payload(data) for data in uart.writes] == [
        [{"event_type": "rotation", "data": 1}],
        [{"event_type": "rotation", "data": 2}],
    ]
    assert sleeper.calls == [0, 0]

    runtime.run_once()
    assert len(uart.writes) == 2


def test_runtime_does_not_duplicate_buffer_entries(runtime_factory):
    runtime, ble, uart, *_ = runtime_factory(
        [[{"event_type": "rotation", "data": 99}]]
    )

    runtime.run_once()
    runtime.run_once()
    assert len(runtime.not_connected_buffer) == 1
    stored = runtime.not_connected_buffer[0]
    assert stored.endswith(END_OF_MESSAGE_DELIMETER)
    assert json.loads(stored[:-1]) == [{"event_type": "rotation", "data": 99}]
