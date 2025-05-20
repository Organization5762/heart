import math
import time

import numba as nb
import numpy as np
import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@nb.njit(fastmath=True)
def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


@nb.njit(fastmath=True)
def patterns(x: float, y: float, t: float) -> float:
    """Calculate pattern value based on coordinates and time."""
    return math.sin(x * x / 0.03 + y * y / 0.03 - t)


@nb.njit(fastmath=True)
def map_value(
    value: float, min1: float, max1: float, min2: float, max2: float
) -> float:
    """Map a value from one range to another."""
    return min2 + (value - min1) * (max2 - min2) / (max1 - min1)


@nb.njit(fastmath=True)
def cubehelix(x: float, y: float, z: float) -> tuple:
    """Convert color to cubehelix color space."""
    a = y * z * (1.0 - z)
    cosh = math.cos(x + math.pi / 2.0)
    sinh = math.sin(x + math.pi / 2.0)
    return (
        clamp(z + a * (1.78277 * sinh - 0.14861 * cosh), 0.0, 1.0),
        clamp(z - a * (0.29227 * cosh + 0.90649 * sinh), 0.0, 1.0),
        clamp(z + a * (1.97294 * cosh), 0.0, 1.0),
    )


@nb.njit(fastmath=True)
def cubehelix_default(t: float) -> tuple:
    """Generate default cubehelix color."""
    x = map_value(t, 0, 1, 300.0 / 180.0 * math.pi, -240.0 / 180.0 * math.pi)
    return cubehelix(x, 0.5, t)


@nb.njit(fastmath=True)
def cubehelix_rainbow(t: float) -> tuple:
    """Generate rainbow cubehelix color."""
    if t < 0.0 or t > 1.0:
        t -= math.floor(t)
    ts = abs(t - 0.5)
    x = (360.0 * t - 100.0) / 180.0 * math.pi
    return cubehelix(x, 1.5 - 1.5 * ts, 0.8 - 0.9 * ts)


@nb.njit(fastmath=True, parallel=True)
def generate_pattern(width: int, height: int, current_time: float) -> np.ndarray:
    """Generate the pattern as a numpy array."""
    # Create output array (RGB)
    output = np.empty((height, width, 3), dtype=np.uint8)

    # Generate pattern for each pixel
    for y in nb.prange(height):
        for x in range(width):
            # Normalize coordinates to -1 to 1 range
            uv_x = (x - width / 2) / height
            uv_y = (y - height / 2) / height

            # Calculate pattern value
            col = patterns(uv_x, uv_y, current_time * 1.5)

            # Map pattern value to color range
            c1 = map_value(col, -1.0, 1.0, 0.0, 0.9)

            # Get color from cubehelix rainbow
            r, g, b = cubehelix_rainbow(c1)

            # Convert to 0-255 range and set color
            output[y, x, 0] = int(clamp(r * 255, 0, 255))
            output[y, x, 1] = int(clamp(g * 255, 0, 255))
            output[y, x, 2] = int(clamp(b * 255, 0, 255))

    return output


class MulticolorRenderer(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.start_time = None

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Process and render the multicolor scene.

        Args:
            window: The pygame surface to render to
            clock: The pygame clock for timing
            peripheral_manager: Manager for accessing peripheral devices
            orientation: The current device orientation

        """
        # Get window dimensions
        width, height = window.get_size()

        # Generate pattern using JIT-compiled function
        pattern_array = generate_pattern(width, height, time.time())

        # Convert numpy array to pygame surface
        pattern_surface = pygame.surfarray.make_surface(pattern_array)

        # Draw the pattern surface to the window
        window.blit(pattern_surface, (0, 0))
