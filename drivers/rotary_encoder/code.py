"""Expose a testable entry point for the rotary encoder driver.

REPL reproduction:
    1. Connect to the board REPL and import this module.
    2. Call ``create_handler()`` to construct the hardware adapter.
    3. Iterate ``read_events(handler)`` while turning the encoder or pressing the
       switch to verify event output without running the full game runtime.
"""

from __future__ import annotations

import board
import rotaryio
from digitalio import DigitalInOut, Direction, Pull

from heart.firmware_io import device_id, identity, rotary_encoder
from heart.utilities.logging import get_logger

DEVICE_NAME = "rotary-encoder"
IDENTITY = identity.Identity(
    device_name=DEVICE_NAME,
    firmware_commit=identity.default_firmware_commit(),
    device_id=device_id.persistent_device_id(),
)
DEBUG = False
logger = get_logger(__name__)


def _debug(message: str) -> None:
    if DEBUG:
        logger.debug(message)


def _write_serial_bus(message: str) -> None:
    """Emit the event payload over the serial bus.

    Do not route event payloads through ``_debug``; the host depends on these
    lines arriving over the serial connection.
    """

    print(message)


def respond_to_identify_query(*, stdin=None, print_fn=print) -> bool:
    """Process any pending Identify query."""

    return identity.poll_and_respond(IDENTITY, stdin=stdin, print_fn=print_fn)


def create_handler(
    *,
    board_module=board,
    rotary_module=rotaryio,
    digital_in_out_cls=DigitalInOut,
    direction=Direction,
    pull=Pull,
) -> rotary_encoder.RotaryEncoderHandler:
    """Initialise the hardware handler for the Trinkey rotary encoder."""

    encoder = rotary_module.IncrementalEncoder(
        pin_a=board_module.ROTA,
        pin_b=board_module.ROTB,
    )

    switch = digital_in_out_cls(board_module.SWITCH)
    switch.direction = direction.INPUT
    switch.pull = pull.DOWN

    return rotary_encoder.RotaryEncoderHandler(encoder, switch, 0)


def read_events(handler: rotary_encoder.RotaryEncoderHandler) -> list[str]:
    """Collect a batch of events from *handler*."""

    return list(handler.handle())


def main() -> None:  # pragma: no cover - exercised on hardware
    handler = create_handler()
    while True:
        respond_to_identify_query()
        for event in read_events(handler):
            _write_serial_bus(event)


if __name__ == "__main__":  # pragma: no cover - exercised on hardware
    main()
