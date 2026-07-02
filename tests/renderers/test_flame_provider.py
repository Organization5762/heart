from __future__ import annotations

from dataclasses import dataclass

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.flame.provider import FlameStateProvider
from heart.renderers.flame.state import FlameState


@dataclass(frozen=True, slots=True)
class _Clock:
    delta_ms: float

    def get_time(self) -> float:
        return self.delta_ms

    def get_fps(self) -> float:
        return 60.0


def test_flame_provider_retains_latest_state_with_value() -> None:
    provider = FlameStateProvider()
    manager = PeripheralManager()
    observed: list[FlameState] = []

    provider.observable(manager).subscribe(observed.append)
    initial = provider.latest_state
    manager.input_io.frame_ticks.advance(_Clock(delta_ms=20.0))

    assert observed[0] == initial
    assert provider.latest_state == observed[-1]
    assert provider.latest_state.dt_seconds == 0.02
