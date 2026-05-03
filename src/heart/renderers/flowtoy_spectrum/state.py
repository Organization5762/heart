from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FlowToySpectrumStop:
    t: float
    hex: str


@dataclass(frozen=True, slots=True)
class FlowToySpectrumState:
    group_id: int = 0
    page: int = 0
    mode: int = 0
    mode_name: str = "flowtoy-unknown"
    display_name: str = "unknown"
    elapsed_s: float = 0.0
    color_spectrum: tuple[FlowToySpectrumStop, ...] = field(default_factory=tuple)
