"""Expose a testable entry point for the rotary encoder driver."""

from __future__ import annotations

import board
import rotaryio
from digitalio import DigitalInOut, Direction, Pull

from heart.firmware_io import rotary_encoder


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
        for event in read_events(handler):
            print(event)


if __name__ == "__main__":  # pragma: no cover - exercised on hardware
    main()
