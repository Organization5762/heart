"""Configuration primitives for :class:`PeripheralManager`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol, Sequence

from heart.peripheral.core import Peripheral

DetectorFactory = Callable[[], Iterable[Peripheral[Any]]]


class GraphNodeFactory(Protocol):
    def __call__(self, *, start_immediately: bool, on_detect: Any | None) -> Any: ...


@dataclass(frozen=True)
class PeripheralConfiguration:
    """Declarative description of a peripheral detection plan."""

    detectors: Sequence[DetectorFactory]
    graph_nodes: Sequence[GraphNodeFactory] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "detectors", tuple(self.detectors))
        object.__setattr__(self, "graph_nodes", tuple(self.graph_nodes))
