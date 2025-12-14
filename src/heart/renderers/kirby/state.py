from dataclasses import dataclass

from heart.renderers import BaseRenderer


@dataclass
class KirbyState:
    scenes: list[BaseRenderer]
