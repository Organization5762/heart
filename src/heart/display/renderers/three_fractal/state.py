from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heart.display.renderers.three_fractal.renderer import FractalRuntime


@dataclass
class FractalSceneState:
    runtime: "FractalRuntime"
