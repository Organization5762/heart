from dataclasses import dataclass

from heart.display.color import Color


@dataclass
class BorderState:
    color: Color


@dataclass
class RainState:
    starting_point: int = 0
    current_y: int = 0


@dataclass
class SlinkyState:
    starting_point: int = 0
    current_y: int = 0
