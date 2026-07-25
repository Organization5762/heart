from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from manyfold import NoopSubscription, Subscribable

from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.input.debug import InputDebugStage, InputDebugTap

PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]
InputMapper = Callable[[Any], Input | None]
PeripheralPredicate = Callable[[Peripheral[Any]], bool]

PERIPHERAL_INPUT_DISPATCH_STREAM = "peripheral.input.dispatch"


@dataclass(frozen=True, slots=True)
class PeripheralInputDispatch:
    event_type: str
    target_count: int


class PeripheralInputBus:
    """Route stream-derived input events into matching peripherals."""

    def __init__(
        self,
        *,
        debug_tap: InputDebugTap,
        peripheral_source: PeripheralSource,
    ) -> None:
        self._debug_tap = debug_tap
        self._peripheral_source = peripheral_source

    def bind(
        self,
        source: Subscribable[Any],
        mapper: InputMapper,
        target: PeripheralPredicate | None = None,
    ) -> Any:
        targets = self._matching_peripherals(target)
        if not targets:
            return NoopSubscription()

        def dispatch(value: Any) -> None:
            input_event = mapper(value)
            if input_event is None:
                return
            for peripheral in targets:
                peripheral.handle_input(input_event)
            self._debug_tap.publish(
                stage=InputDebugStage.LOGICAL,
                stream_name=PERIPHERAL_INPUT_DISPATCH_STREAM,
                source_id=input_event.event_type,
                payload=PeripheralInputDispatch(
                    event_type=input_event.event_type,
                    target_count=len(targets),
                ),
                upstream_ids=("peripheral.input",),
            )

        return source.subscribe(dispatch)

    def _matching_peripherals(
        self,
        target: PeripheralPredicate | None,
    ) -> tuple[Peripheral[Any], ...]:
        predicate = target or (lambda _peripheral: True)
        return tuple(
            peripheral
            for peripheral in self._peripheral_source()
            if predicate(peripheral)
        )
