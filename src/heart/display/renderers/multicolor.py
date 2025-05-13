import pygame
import math
import numpy as np
import time

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def patterns(z: tuple[float, float], t: float) -> float:
    """Calculate pattern value based on coordinates and time."""
    x, y = z
    return math.sin(x * x / 0.03 + y * y / 0.03 - t)


def map_value(value: float, min1: float, max1: float, min2: float, max2: float) -> float:
    """Map a value from one range to another."""
    return min2 + (value - min1) * (max2 - min2) / (max1 - min1)


def cubehelix(c: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert color to cubehelix color space."""
    x, y, z = c
    a = y * z * (1.0 - z)
    cosh = math.cos(x + math.pi / 2.0)
    sinh = math.sin(x + math.pi / 2.0)
    return (
        clamp(z + a * (1.78277 * sinh - 0.14861 * cosh), 0.0, 1.0),
        clamp(z - a * (0.29227 * cosh + 0.90649 * sinh), 0.0, 1.0),
        clamp(z + a * (1.97294 * cosh), 0.0, 1.0)
    )


def cubehelix_default(t: float) -> tuple[float, float, float]:
    """Generate default cubehelix color."""
    x = map_value(t, 0, 1, 300.0 / 180.0 * math.pi, -240.0 / 180.0 * math.pi)
    return cubehelix((x, 0.5, t))


def cubehelix_rainbow(t: float) -> tuple[float, float, float]:
    """Generate rainbow cubehelix color."""
    if t < 0.0 or t > 1.0:
        t -= math.floor(t)
    ts = abs(t - 0.5)
    x = (360.0 * t - 100.0) / 180.0 * math.pi
    return cubehelix((x, 1.5 - 1.5 * ts, 0.8 - 0.9 * ts))


class MulticolorRenderer(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.start_time = None

    def _initialize(self) -> None:
        """Initialize any resources needed for rendering."""
        self.initialized = True

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
        if not self.initialized:
            self._initialize()
        
        # Get window dimensions
        width, height = window.get_size()
        
        # Create a surface for the pattern
        pattern_surface = pygame.Surface((width, height))
        
        # Generate pattern for each pixel
        for y in range(height):
            for x in range(width):
                # Normalize coordinates to -1 to 1 range
                uv_x = (x - width/2) / height
                uv_y = (y - height/2) / height
                
                # Calculate pattern value
                col = patterns((uv_x, uv_y), time.time() * 1.5)
                
                # Map pattern value to color range
                c1 = map_value(col, -1.0, 1.0, 0.0, 0.9)
                
                # Get color from cubehelix rainbow
                r, g, b = cubehelix_rainbow(c1)
                
                # Convert to 0-255 range and create color
                color = (
                    int(clamp(r * 255, 0, 255)),
                    int(clamp(g * 255, 0, 255)),
                    int(clamp(b * 255, 0, 255))
                )
                
                pattern_surface.set_at((x, y), color)
        
        # Draw the pattern surface to the window
        window.blit(pattern_surface, (0, 0)) 