from dataclasses import dataclass
from functools import cached_property

import pygame
from PIL import Image


@dataclass
class Layout:
    columns: int
    rows: int


class Orientation:
    def get_type(self) -> type["Orientation"]:
        return type(self)

    def __init__(self, layout: Layout):
        self.layout = layout


class Rectangle(Orientation):
    @classmethod
    def with_layout(cls, columns: int, rows: int) -> "Rectangle":
        return cls(layout=Layout(columns, rows))


class Cube(Orientation):
    @classmethod
    def sides(cls) -> "Cube":
        """I.e.

        the 4 "walls" of a cube

        """
        return cls(layout=Layout(4, 1))


@dataclass
class Device:
    orientation: Orientation

    def individual_display_size(self) -> tuple[int, int]:
        raise NotImplementedError("")

    def full_display_size(self) -> tuple[int, int]:
        return (
            self.individual_display_size()[0] * self.orientation.layout.columns,
            self.individual_display_size()[1] * self.orientation.layout.rows,
        )

    def scaled_display_size(self) -> tuple[int, int]:
        return (
            self.full_display_size()[0] * self.scale_factor,
            self.full_display_size()[1] * self.scale_factor,
        )

    @cached_property
    def scale_factor(self) -> int:
        return 1

    def set_screen(self, screen: pygame.Surface) -> None:
        pass

    def set_image(self, image: Image.Image) -> None:
        pass
