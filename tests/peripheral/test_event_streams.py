"""Tests for peripheral reactive event streams."""

from __future__ import annotations

from typing import Any

import reactivex
from reactivex.disposable import Disposable

from heart.peripheral.core import Peripheral


class CountingPeripheral(Peripheral[int]):
    """Capture subscription counts so shared streams avoid duplicate work."""

    def __init__(self, counter: dict[str, int]) -> None:
        self._counter = counter

    def _event_stream(self) -> reactivex.Observable[int]:
        def on_subscribe(observer: Any, scheduler: Any) -> Disposable:
            self._counter["subscriptions"] += 1
            return Disposable()

        return reactivex.create(on_subscribe)


class TestPeripheralObserveSharing:
    """Group tests for shared peripheral streams to keep reactive fan-out efficient."""

    def test_observe_shares_subscription(self) -> None:
        """Ensure observe shares a single subscription so redundant polling is avoided for scalability."""
        counter = {"subscriptions": 0}
        peripheral = CountingPeripheral(counter)
        stream = peripheral.observe

        subscription_a = stream.subscribe()
        subscription_b = stream.subscribe()
        try:
            assert counter["subscriptions"] == 1, "Observe should share the underlying stream."
        finally:
            subscription_a.dispose()
            subscription_b.dispose()
