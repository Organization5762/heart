from dataclasses import dataclass

from heart.renderers import BaseRenderer


@dataclass
class ArtistState:
    scenes: list[BaseRenderer]
