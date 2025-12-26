import math
import time
from dataclasses import dataclass

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.mandelbrot.scene import get_mandelbrot_converge_time
from heart.utilities.env import Configuration
from heart.utilities.env.enums import MandelbrotInteriorStrategy
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_ITERATIONS = 200
PALETTE_SIZE = 256
PALETTE_CYCLE_LENGTH = 64
REAL_CENTER = -0.5
REAL_HALF_RANGE = 1.75
IMAG_HALF_RANGE = 1.5
ROTATION_SPEED = 0.15


@dataclass(frozen=True)
class CubeMandelbrotState:
    base_azimuths: np.ndarray
    elevations: np.ndarray
    palette: np.ndarray
    max_iterations: int
    start_time: float
    face_width: int
    face_height: int
    face_count: int


def _generate_palette(num_colors: int, cycle_length: int) -> np.ndarray:
    base_exponents = (0.5, 2.0, 0.8)
    colors = np.zeros((num_colors, 3), dtype=np.uint8)
    for i in range(1, num_colors):
        r_exp, g_exp, b_exp = base_exponents
        cycle_i = i % cycle_length
        t = cycle_i / cycle_length

        r = int(255 * (t**r_exp))
        g = int(255 * (t**g_exp))
        b = int(255 * (t**b_exp))

        pulse = 0.5 + 0.5 * np.sin(2 * np.pi * i / cycle_length)
        r = min(255, int(r * (1.1 + 0.2 * pulse)))
        g = min(255, int(g * (0.7 + 0.2 * pulse)))
        b = min(255, int(b * (1.0 + 0.3 * pulse)))
        colors[i] = (r, g, b)
    return colors


def _build_cube_angles(
    face_width: int, face_height: int, face_count: int
) -> tuple[np.ndarray, np.ndarray]:
    u_vals = np.linspace(-1.0, 1.0, face_width, dtype=np.float32)
    v_vals = np.linspace(1.0, -1.0, face_height, dtype=np.float32)
    u_grid, v_grid = np.meshgrid(u_vals, v_vals)
    z_grid = np.ones_like(u_grid)

    length = np.sqrt(u_grid**2 + v_grid**2 + z_grid**2)
    x_base = u_grid / length
    y_base = v_grid / length
    z_base = z_grid / length

    azimuths = np.zeros((face_height, face_width * face_count), dtype=np.float32)
    elevations = np.zeros_like(azimuths)

    for face_index in range(face_count):
        angle = (2 * math.pi / face_count) * face_index
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        x_rot = x_base * cos_angle + z_base * sin_angle
        z_rot = -x_base * sin_angle + z_base * cos_angle
        azimuth = np.arctan2(x_rot, z_rot)
        elevation = np.arcsin(np.clip(y_base, -1.0, 1.0))
        start = face_index * face_width
        end = start + face_width
        azimuths[:, start:end] = azimuth
        elevations[:, start:end] = elevation

    return azimuths, elevations


class CubeMandelbrotRenderer(StatefulBaseRenderer[CubeMandelbrotState]):
    """Render a mandelbrot field wrapped around cube faces."""

    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.mandelbrot_interior_strategy = (
            Configuration.mandelbrot_interior_strategy()
        )
        self.use_mandelbrot_interior = (
            self.mandelbrot_interior_strategy == MandelbrotInteriorStrategy.CARDIOID
        )

    def _create_initial_state(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> CubeMandelbrotState:
        width, height = window.get_size()
        face_count = max(1, orientation.layout.columns)
        face_width = width // face_count
        face_height = height // max(1, orientation.layout.rows)

        base_azimuths, elevations = _build_cube_angles(
            face_width=face_width,
            face_height=face_height,
            face_count=face_count,
        )
        palette = _generate_palette(PALETTE_SIZE, PALETTE_CYCLE_LENGTH)
        max_iterations = min(DEFAULT_MAX_ITERATIONS, palette.shape[0] - 1)

        return CubeMandelbrotState(
            base_azimuths=base_azimuths,
            elevations=elevations,
            palette=palette,
            max_iterations=max_iterations,
            start_time=time.monotonic(),
            face_width=face_width,
            face_height=face_height,
            face_count=face_count,
        )

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        elapsed = time.monotonic() - self.state.start_time
        rotation = elapsed * ROTATION_SPEED
        azimuths = self.state.base_azimuths + rotation
        azimuths = (azimuths + math.pi) % (2 * math.pi) - math.pi

        re = REAL_CENTER + (azimuths / math.pi) * REAL_HALF_RANGE
        im = (self.state.elevations / (math.pi / 2)) * IMAG_HALF_RANGE

        iterations = get_mandelbrot_converge_time(
            re,
            im,
            0.0,
            0.0,
            self.state.max_iterations,
            self.use_mandelbrot_interior,
        )

        clipped = np.clip(iterations, 0, self.state.palette.shape[0] - 1)
        color_surface = self.state.palette[clipped]
        surface_array = np.transpose(color_surface, (1, 0, 2))
        pygame.surfarray.blit_array(window, surface_array)
