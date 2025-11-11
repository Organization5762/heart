from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class SlidingImageState:
    image: pygame.Surface | None = None
    offset: int = 0
    speed: int = 1
    width: int = 0


class SlidingImage(AtomicBaseRenderer[SlidingImageState]):
    """Render a 256×64 image that continuously slides horizontally.

    The renderer operates in *FULL* display mode so it receives the complete
    256×64 surface (four 64×64 cube faces laid out left→right).
    Each frame the image is shifted `speed` pixels to the **left**; once the
    offset reaches the image width it wraps to 0, creating an endless loop
    around the cube sides.

    """

    def __init__(self, image_file: str, *, speed: int = 1) -> None:
        self._configured_speed = max(1, speed)
        self.file = image_file

        AtomicBaseRenderer.__init__(self)
        # We want to draw across the full 4-face surface
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(self) -> SlidingImageState:
        return SlidingImageState(speed=self._configured_speed)

    # ---------------------------------------------------------------------
    # lifecycle hooks
    # ---------------------------------------------------------------------
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # load and scale once we know the LED surface size
        image = Loader.load(self.file)
        image = pygame.transform.scale(image, window.get_size())
        width, _ = image.get_size()
        self.update_state(image=image, width=width)
        super().initialize(window, clock, peripheral_manager, orientation)

    # ---------------------------------------------------------------------
    # main draw routine
    # ---------------------------------------------------------------------
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        state = self.state
        image = state.image
        if image is None or state.width == 0:
            # should not happen – initialize() guarantees loading
            return

        # advance offset and wrap
        offset = (state.offset + state.speed) % state.width
        self.update_state(offset=offset)

        # First blit: main image shifted left by current offset
        window.blit(image, (-offset, 0))

        # Second blit: fill the gap on the right with the wrapped part
        if offset:
            window.blit(image, (state.width - offset, 0))

    def reset(self) -> None:
        state = self.state
        if state.image is None or state.width == 0:
            super().reset()
            return

        self.update_state(offset=0, speed=self._configured_speed)


@dataclass
class SlidingRendererState:
    offset: int = 0
    speed: int = 1


class SlidingRenderer(AtomicBaseRenderer[SlidingRendererState]):
    """Render a 256×64 image that continuously slides horizontally.

    The renderer operates in *FULL* display mode so it receives the complete
    256×64 surface (four 64×64 cube faces laid out left→right).
    Each frame the image is shifted `speed` pixels to the **left**; once the
    offset reaches the image width it wraps to 0, creating an endless loop
    around the cube sides.

    """

    def __init__(self, renderer: BaseRenderer, *, speed: int = 1) -> None:
        self._configured_speed = max(1, speed)
        self.composed = renderer

        AtomicBaseRenderer.__init__(self)
        # We want to draw across the full 4-face surface
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(self) -> SlidingRendererState:
        return SlidingRendererState(speed=self._configured_speed)

    # ---------------------------------------------------------------------
    # lifecycle hooks
    # ---------------------------------------------------------------------
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.composed.initialize(window, clock, peripheral_manager, orientation)
        super().initialize(window, clock, peripheral_manager, orientation)

    # ---------------------------------------------------------------------
    # main draw routine
    # ---------------------------------------------------------------------
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.composed._internal_process(window, clock, peripheral_manager, orientation)

        state = self.state
        img_w, _ = window.get_size()
        # advance offset and wrap
        offset = (state.offset + state.speed) % img_w
        self.update_state(offset=offset)

        # Copy window
        surface = window.copy()

        window.fill((0, 0, 0, 0))
        # First blit: main image shifted left by current offset
        window.blit(surface, (-offset, 0))

        # Second blit: fill the gap on the right with the wrapped part
        if offset:
            window.blit(surface, (img_w - offset, 0))
