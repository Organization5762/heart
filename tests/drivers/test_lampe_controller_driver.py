from driver_loader import load_driver_module, make_module


class FakeDigitalInOut:
    def __init__(self, pin):
        self.pin = pin
        self.direction = None
        self.pull = None

    def switch_to_input(self, pull):
        self.pull = pull


class FakeDirection:
    OUTPUT = "output"


class FakePull:
    UP = "up"
    DOWN = "down"


class FakeI2C:
    def __init__(self, *_args, **_kwargs):
        pass


class FakeSeesaw:
    INPUT_PULLUP = "pullup"

    def __init__(self, *_args, **_kwargs):
        pass


class FakeIncrementalEncoder:
    def __init__(self, *_args, **_kwargs):
        pass


class FakeDigitalIO:
    def __init__(self, *_args, **_kwargs):
        self.pull = None

    def switch_to_input(self, pull):
        self.pull = pull


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


advertising_standard = make_module(
    "adafruit_ble.advertising.standard", ProvideServicesAdvertisement=FakeAdvertisement
)
advertising_module = make_module("adafruit_ble.advertising", standard=advertising_standard)
services_nordic = make_module("adafruit_ble.services.nordic", UARTService=FakeUARTService)
services_module = make_module("adafruit_ble.services", nordic=services_nordic)

adafruit_seesaw_module = make_module(
    "adafruit_seesaw",
    seesaw=make_module("adafruit_seesaw.seesaw", Seesaw=FakeSeesaw),
    rotaryio=make_module("adafruit_seesaw.rotaryio", IncrementalEncoder=FakeIncrementalEncoder),
    digitalio=make_module("adafruit_seesaw.digitalio", DigitalIO=FakeDigitalIO),
)

STUBS = {
    "board": make_module("board", LED="led", SCL="scl", SDA="sda"),
    "digitalio": make_module(
        "digitalio", DigitalInOut=FakeDigitalInOut, Direction=FakeDirection, Pull=FakePull
    ),
    "busio": make_module("busio", I2C=FakeI2C),
    "adafruit_seesaw": adafruit_seesaw_module,
    "adafruit_seesaw.seesaw": adafruit_seesaw_module.seesaw,
    "adafruit_seesaw.rotaryio": adafruit_seesaw_module.rotaryio,
    "adafruit_seesaw.digitalio": adafruit_seesaw_module.digitalio,
    "adafruit_ble": make_module(
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

lampe_controller = load_driver_module("lampe-controller", stubs=STUBS)
LampeControllerRuntime = lampe_controller.LampeControllerRuntime


class StubSeesawController:
    def __init__(self, batches):
        self._batches = list(batches)

    def handle(self):
        if self._batches:
            batch = self._batches.pop(0)
        else:
            batch = []
        for event in batch:
            yield event


class StubSender:
    def __init__(self):
        self.calls = []

    def __call__(self, events):
        self.calls.append(list(events))


def test_runtime_sends_events_to_bluetooth():
    controller = StubSeesawController([["a"], ["b", "c"]])
    sender = StubSender()
    runtime = LampeControllerRuntime(controller, sender)

    runtime.run_once()
    runtime.run_once()

    assert sender.calls == [["a"], ["b", "c"]]


def test_runtime_handles_empty_batches():
    controller = StubSeesawController([[]])
    sender = StubSender()
    runtime = LampeControllerRuntime(controller, sender)

    runtime.run_once()

    assert sender.calls == [[]]
