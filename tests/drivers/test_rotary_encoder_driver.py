import importlib
import io
import json

import pytest
from driver_loader import load_driver_module, make_module, temporary_modules

from heart.firmware_io import constants


class FakeDigitalInOut:
    def __init__(self, pin):
        self.pin = pin
        self.direction = None
        self.pull = None


class FakeDirection:
    INPUT = "input"


class FakePull:
    UP = "up"
    DOWN = "down"


digitalio_stub = make_module(
    "digitalio", DigitalInOut=FakeDigitalInOut, Direction=FakeDirection, Pull=FakePull
)

with temporary_modules({"digitalio": digitalio_stub}):
    rotary_encoder = importlib.import_module("heart.firmware_io.rotary_encoder")


class StubRotaryModule:
    class IncrementalEncoder:
        def __init__(self, *, pin_a, pin_b):
            self.pin_a = pin_a
            self.pin_b = pin_b
            self.position = 0


STUBS = {
    "board": make_module("board", ROTA="rota", ROTB="rotb", SWITCH="switch"),
    "rotaryio": make_module("rotaryio", IncrementalEncoder=StubRotaryModule.IncrementalEncoder),
    "digitalio": digitalio_stub,
}


@pytest.fixture()
def rotary_driver(monkeypatch, tmp_path):
    device_id_path = tmp_path / "device_id.txt"
    monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
    monkeypatch.setenv("HEART_DEVICE_ID", "rotary-encoder-test-id")
    module = load_driver_module("rotary_encoder", stubs=STUBS)
    return module


class StubDigitalInOut:
    instances = []

    def __init__(self, pin):
        self.pin = pin
        self.direction = None
        self.pull = None
        StubDigitalInOut.instances.append(self)


class StubHandler:
    def __init__(self, events):
        self._events = events

    def handle(self):
        yield from self._events


class TestDriversRotaryEncoderDriver:
    """Group Drivers Rotary Encoder Driver tests so drivers rotary encoder driver behaviour stays reliable. This preserves confidence in drivers rotary encoder driver for end-to-end scenarios."""

    def test_create_handler_uses_injected_modules(self, rotary_driver):
        """Verify that create_handler uses the provided modules to configure the rotary encoder handler. This keeps hardware abstraction swappable so deployments can tailor pin assignments."""
        StubDigitalInOut.instances.clear()
        handler = rotary_driver.create_handler(
            board_module=make_module("board", ROTA="rota", ROTB="rotb", SWITCH="switch"),
            rotary_module=StubRotaryModule,
            digital_in_out_cls=StubDigitalInOut,
            direction=FakeDirection,
            pull=FakePull,
        )

        assert isinstance(handler, rotary_encoder.RotaryEncoderHandler)
        assert len(StubDigitalInOut.instances) == 1
        created_switch = StubDigitalInOut.instances[0]
        assert created_switch.direction == FakeDirection.INPUT
        assert created_switch.pull == FakePull.DOWN



    def test_read_events_returns_handler_values(self, rotary_driver):
        """Verify that read_events returns the events produced by the handler iterable. This ensures driver plumbing forwards physical interactions without modification."""
        handler = StubHandler(["event1", "event2"])
        assert rotary_driver.read_events(handler) == ["event1", "event2"]



    def test_rotary_driver_emits_identity_payload(self, rotary_driver):
        """Verify that respond_to_identify_query prints the rotary encoder driver identity payload. This aids device discovery so orchestration tools can label encoder modules."""
        stream = io.StringIO("Identify\n")
        outputs: list[str] = []

        handled = rotary_driver.respond_to_identify_query(stdin=stream, print_fn=outputs.append)

        assert handled is True
        payload = json.loads(outputs[0])
        assert payload["event_type"] == constants.DEVICE_IDENTIFY
        assert payload["data"]["device_name"] == rotary_driver.IDENTITY.device_name
        assert payload["data"]["device_id"] == "rotary-encoder-test-id"
