"""Tests covering automatic renderer input bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.events.types import AccelerometerVector
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.switch import SwitchState


@dataclass(frozen=True)
class _DummyState:
    seen: tuple[str, ...] = ()


class _EventCapturingRenderer(AtomicBaseRenderer[_DummyState]):
    """Renderer that records accelerometer vectors via automatic listeners."""

    def __init__(self) -> None:
        self.vectors: list[tuple[float, float, float]] = []
        super().__init__()
        self.register_event_listener(
            AccelerometerVector.EVENT_TYPE, self._handle_accelerometer
        )

    def _create_initial_state(self) -> _DummyState:
        return _DummyState()

    def _handle_accelerometer(self, event: Input) -> None:
        payload = event.data
        if isinstance(payload, AccelerometerVector):
            vector = (payload.x, payload.y, payload.z)
        else:
            vector = (
                float(payload["x"]),
                float(payload["y"]),
                float(payload["z"]),
            )
        self.vectors.append(vector)


class _SwitchCachingRenderer(BaseRenderer):
    """Renderer that caches switch state updates for downstream consumers."""

    def __init__(self) -> None:
        super().__init__()
        self.observed: list[SwitchState] = []
        self.enable_switch_state_cache()

    def process(self, window, clock, peripheral_manager, orientation):
        return None

    def on_switch_state(self, state: SwitchState) -> None:
        super().on_switch_state(state)
        self.observed.append(state)


class _StubPeripheralManager:
    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        switch_state: SwitchState | None = None,
    ) -> None:
        self.event_bus = event_bus
        self._switch_state = switch_state
        self._switch_callbacks: list[Callable[[SwitchState], None]] = []

    def subscribe_main_switch(self, callback):
        self._switch_callbacks.append(callback)

        def _unsubscribe() -> None:
            try:
                self._switch_callbacks.remove(callback)
            except ValueError:
                pass

        return _unsubscribe

    def get_main_switch_state(self) -> SwitchState:
        if self._switch_state is None:
            raise RuntimeError("Main switch not available")
        return self._switch_state

    def emit_switch(self, state: SwitchState) -> None:
        self._switch_state = state
        for callback in list(self._switch_callbacks):
            callback(state)


def test_event_listener_activation_updates_cache() -> None:
    """Ensure register_event_listener attaches callbacks when bindings activate."""

    renderer = _EventCapturingRenderer()
    bus = EventBus()
    manager = _StubPeripheralManager(event_bus=bus)

    renderer.ensure_input_bindings(manager)
    bus.emit(
        AccelerometerVector.EVENT_TYPE,
        {"x": 0.1, "y": -0.2, "z": 9.7},
    )

    assert renderer.vectors == [(0.1, -0.2, 9.7)]


def test_switch_state_cache_tracks_updates() -> None:
    """Verify enable_switch_state_cache replays and tracks switch snapshots."""

    initial = SwitchState(0, 0, 0, 0, 0)
    updated = SwitchState(1, 2, 3, 4, 5)
    manager = _StubPeripheralManager(switch_state=initial)
    renderer = _SwitchCachingRenderer()

    renderer.ensure_input_bindings(manager)

    assert renderer.get_switch_state() == initial
    manager.emit_switch(updated)
    assert renderer.get_switch_state() == updated
    assert updated in renderer.observed
