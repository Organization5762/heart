import io
import json

import pytest
from driver_loader import load_driver_module, make_module

from heart.firmware_io import constants


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


@pytest.fixture()
def lampe_controller(monkeypatch, tmp_path):
    device_id_path = tmp_path / "device_id.txt"
    monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
    monkeypatch.setenv("HEART_DEVICE_ID", "lampe-controller-test-id")
    module = load_driver_module("lampe-controller", stubs=STUBS)
    return module


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


class TestDriversLampeControllerDriver:
    """Group Drivers Lampe Controller Driver tests so drivers lampe controller driver behaviour stays reliable. This preserves confidence in drivers lampe controller driver for end-to-end scenarios."""

    def test_runtime_sends_events_to_bluetooth(self, lampe_controller):
        """Verify that LampeControllerRuntime forwards controller events through the BLE sender. This ensures hand inputs reach paired devices so lighting interactions stay responsive."""
        controller = StubSeesawController([["a"], ["b", "c"]])
        sender = StubSender()
        runtime = lampe_controller.LampeControllerRuntime(controller, sender)

        runtime.run_once()
        runtime.run_once()

        assert sender.calls == [["a"], ["b", "c"]]



    def test_runtime_handles_empty_batches(self, lampe_controller):
        """Verify that LampeControllerRuntime still sends an empty batch when no events are produced. This keeps the protocol well-formed so idle periods do not stall the receiver."""
        controller = StubSeesawController([[]])
        sender = StubSender()
        runtime = lampe_controller.LampeControllerRuntime(controller, sender)

        runtime.run_once()

        assert sender.calls == [[]]



    def test_respond_to_identify_query_emits_identity_payload(self, lampe_controller):
        """Verify that respond_to_identify_query prints the Lampe controller identity payload. This allows operations tooling to discover deployed controllers for diagnostics."""
        stream = io.StringIO("Identify\n")
        outputs: list[str] = []

        handled = lampe_controller.respond_to_identify_query(stdin=stream, print_fn=outputs.append)

        assert handled is True
        payload = json.loads(outputs[0])
        assert payload["event_type"] == constants.DEVICE_IDENTIFY
        assert payload["data"]["device_name"] == lampe_controller.IDENTITY.device_name
        assert payload["data"]["device_id"] == "lampe-controller-test-id"



    def test_runtime_invokes_identify_responder(self, monkeypatch, lampe_controller):
        """Verify that the runtime asks respond_to_identify_query to handle identify requests. This keeps runtime logic composable so new commands stay centralized."""
        calls = []

        def responder(**_kwargs):
            calls.append(True)
            return False

        monkeypatch.setattr(lampe_controller, "respond_to_identify_query", responder)

        controller = StubSeesawController([["ignored"]])
        sender = StubSender()
        runtime = lampe_controller.LampeControllerRuntime(controller, sender)

        runtime.run_once()

        assert calls
