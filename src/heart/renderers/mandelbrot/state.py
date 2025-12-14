from dataclasses import dataclass
from enum import IntEnum

import pygame

from heart.device import Orientation


class ViewMode(IntEnum):
    MANDELBROT = 0
    MANDELBROT_SELECTED = 1
    JULIA_SELECTED = 2
    JULIA = 3


@dataclass
class AppState:
    movement: pygame.Vector2
    jmovement: pygame.Vector2
    cursor_pos: pygame.Vector2
    jcursor_pos: pygame.Vector2
    msurface_width: int
    msurface_height: int

    num_palettes: int
    init_orientation: Orientation
    orientation: Orientation | None = None
    palette_index: int = 0

    view_mode: ViewMode = ViewMode.MANDELBROT
    selected_surface: str = "mandelbrot"
    critical_point: complex = complex(0, 0)
    max_iterations: int = 250
    show_left_cursor: bool = False
    show_right_cursor: bool = False
    movement_mode: str = "panning"
    zoom: float = 1.0
    jzoom: float = 2.0
    mode: str = "free"
    show_fps: bool = False
    show_debug: bool = False
    julia_mode: bool = False
    julia_constant: complex = complex(-0.7, 0.27)  # Default interesting value
    julia_orbit: list[complex] = None

    def __post_init__(self):
        # self._init_movement = self.movement
        self._init_x = self.movement.x
        self._init_y = self.movement.y
        self._init_max_iterations = self.max_iterations
        self.orientation = self.init_orientation

    def reset(self):
        self.orientation = self.init_orientation
        self.view_mode = ViewMode.MANDELBROT
        self.movement.x = self._init_x
        self.movement.y = self._init_y
        self.jmovement.x = 0.0
        self.jmovement.y = 0.0
        self.max_iterations = self._init_max_iterations
        self.zoom = 1.0
        self.jzoom = 2.0
        self.show_fps = False
        self.show_debug = False

    def set_mode_auto(self):
        self.reset()
        self.mode = "auto"

    def set_mode_free(self):
        self.mode = "free"
