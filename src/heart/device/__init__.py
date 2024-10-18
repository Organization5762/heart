from dataclasses import dataclass
from functools import cached_property

from PIL import Image


@dataclass
class Layout:
    columns: int
    rows: int


@dataclass
class Device:
    layout: Layout

    def individual_display_size(self) -> tuple[int, int]:
        raise NotImplementedError("")

    def full_display_size(self) -> tuple[int, int]:
        return (
            self.individual_display_size()[0] * self.layout.columns,
            self.individual_display_size()[1] * self.layout.rows,
        )

    @cached_property
    def scale_factor(self) -> int:
        return 1

    def set_image(self, image: Image.Image) -> None:
        pass
