from dataclasses import dataclass

from heart.display.renderers import BaseRenderer


@dataclass
class KirbyState:
    scenes: list[BaseRenderer]
