"""Lampe controller firmware entry point."""

from __future__ import annotations

import adafruit_seesaw.digitalio
import adafruit_seesaw.rotaryio
import adafruit_seesaw.seesaw
import board
import busio
import digitalio

from heart.firmware_io import bluetooth, device_id, identity, rotary_encoder

MINIMUM_LIGHT_ON_SECONDS = 0.05


IDENTITY = identity.Identity(
    device_name="lampe-controller",
    firmware_commit=identity.default_firmware_commit(),
    device_id=device_id.persistent_device_id(),
)


def respond_to_identify_query(*, stdin=None, print_fn=print) -> bool:
    """Process any pending Identify query."""

    return identity.poll_and_respond(IDENTITY, stdin=stdin, print_fn=print_fn)


class LampeControllerRuntime:
    """Coordinates the Seesaw and Bluetooth bridge."""

    def __init__(self, seesaw_controller, send_fn, led=None):
        self._seesaw_controller = seesaw_controller
        self._send_fn = send_fn
        self.led = led

    def run_once(self) -> None:
        respond_to_identify_query()
        events = list(self._seesaw_controller.handle())
        self._send_fn(events)


def _initialise_led(board_module=board, digitalio_module=digitalio) -> digitalio.DigitalInOut:
    led = digitalio_module.DigitalInOut(board_module.LED)
    led.direction = digitalio_module.Direction.OUTPUT
    led.value = True
    return led


def _initialise_seesaw(
    *,
    board_module=board,
    busio_module=busio,
    seesaw_module=adafruit_seesaw.seesaw,
    rotary_module=adafruit_seesaw.rotaryio,
    seesaw_digital_module=adafruit_seesaw.digitalio,
    digitalio_module=digitalio,
) -> rotary_encoder.Seesaw:
    i2c = busio_module.I2C(board_module.SCL, board_module.SDA, frequency=50000)
    seesaw = seesaw_module.Seesaw(i2c, 0x49)

    encoders = [rotary_module.IncrementalEncoder(seesaw, n) for n in range(4)]
    switches = [seesaw_digital_module.DigitalIO(seesaw, pin) for pin in (12, 14, 17, 9)]
    for switch in switches:
        switch.switch_to_input(digitalio_module.Pull.UP)

    handlers = [
        rotary_encoder.RotaryEncoderHandler(encoders[index], switches[index], index)
        for index in range(4)
    ]
    return rotary_encoder.Seesaw(handlers)


def create_runtime() -> LampeControllerRuntime:
    led = _initialise_led()
    controller = _initialise_seesaw()
    return LampeControllerRuntime(controller, bluetooth.send, led=led)


def main(runtime: LampeControllerRuntime | None = None) -> None:  # pragma: no cover - hardware only
    runtime = runtime or create_runtime()
    while True:
        runtime.run_once()


if __name__ == "__main__":  # pragma: no cover - exercised on hardware
    main()
