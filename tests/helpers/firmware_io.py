from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class HandlerStep:
    """Represents a single call into a handler with optional state changes."""

    label: str
    position: int | None = None
    switch_value: bool | None = None
    advance: float = 0.0


def run_handler_steps(handler, encoder, switch, steps: Sequence[HandlerStep], clock=None):
    """Execute ``handler.handle`` over ``steps`` recording emitted events."""

    timeline: List[tuple[str, list[str]]] = []
    for step in steps:
        if clock is not None and step.advance:
            clock.advance(step.advance)
        if step.position is not None:
            encoder.position = step.position
        if step.switch_value is not None:
            switch.value = step.switch_value
        timeline.append((step.label, list(handler.handle())))
    return timeline


class StubBLE:
    def __init__(self, *, advertising: bool, connected: bool) -> None:
        self.advertising = advertising
        self.connected = connected
        self.started_advertising_with: list[object] = []

    def start_advertising(self, advertisement) -> None:
        self.started_advertising_with.append(advertisement)
        self.advertising = True


class StubUART:
    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, payload: bytes) -> None:
        self.written.append(payload)


class StubSensor:
    def __init__(self, acceleration=None, gyro=None, magnetic=None) -> None:
        self.acceleration = acceleration
        self.gyro = gyro
        self.magnetic = magnetic
