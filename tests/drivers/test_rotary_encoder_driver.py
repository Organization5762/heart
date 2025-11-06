import importlib

from driver_loader import load_driver_module, make_module, temporary_modules


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

rotary_driver = load_driver_module("rotary_encoder", stubs=STUBS)
create_handler = rotary_driver.create_handler
read_events = rotary_driver.read_events


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


def test_create_handler_uses_injected_modules():
    StubDigitalInOut.instances.clear()
    handler = create_handler(
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


def test_read_events_returns_handler_values():
    handler = StubHandler(["event1", "event2"])
    assert read_events(handler) == ["event1", "event2"]
