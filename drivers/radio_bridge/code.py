"""Minimal firmware stub that forwards radio packets over the USB REPL."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, Mapping

from heart.firmware_io import device_id, identity
from heart.firmware_io.constants import RADIO_PACKET

IDENTITY = identity.Identity(
    device_name="radio-bridge",
    firmware_commit=identity.default_firmware_commit(),
    device_id=device_id.persistent_device_id(),
)


def respond_to_identify_query(*, stdin=None, print_fn=print) -> bool:
    """Process any pending Identify query from the host runtime."""

    return identity.poll_and_respond(IDENTITY, stdin=stdin, print_fn=print_fn)


def _default_packet() -> Mapping[str, object]:
    """Return an empty payload placeholder.

    Real firmware should replace this with a call that pulls data from the
    attached radio transceiver.
    """

    return {}


@dataclass
class RadioBridgeRuntime:
    """Coordinate packet acquisition and USB logging."""

    gather_packet: Callable[[], Mapping[str, object]] = _default_packet
    print_fn: Callable[[str], None] = print
    sleep_fn: Callable[[float], None] = time.sleep
    interval_seconds: float = 0.1

    def _encode_payload(self, payload: Mapping[str, object]) -> str:
        frame = {"event_type": RADIO_PACKET, "data": dict(payload)}
        return json.dumps(frame) + "\n"

    def run_once(self) -> None:
        respond_to_identify_query()
        payload = self.gather_packet()
        self.print_fn(self._encode_payload(payload))
        self.sleep_fn(self.interval_seconds)


def main(runtime: RadioBridgeRuntime | None = None) -> None:
    runtime = runtime or RadioBridgeRuntime()
    while True:
        runtime.run_once()


if __name__ == "__main__":  # pragma: no cover - executed on-device
    main()
