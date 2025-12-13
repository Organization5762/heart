from dataclasses import dataclass

from heart.display.renderers import BaseRenderer


@dataclass
class ArtistState:
    scenes: list[BaseRenderer]
