from heart.display.renderers import BaseRenderer
import pygame
from heart.peripheral.core.manager import PeripheralManager
from heart.device import Orientation
from heart import DeviceDisplayMode

class SlideTransitionRenderer(BaseRenderer):
    """
    Slides renderer_B into view while renderer_A moves out.
    direction  =  1  → B comes from the right  (A → left)
    direction  = -1  → B comes from the left   (A → right)
    """

    def __init__(
        self,
        renderer_A: BaseRenderer,
        renderer_B: BaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 2,
    ) -> None:
        super().__init__()
        self.renderer_A = renderer_A
        self.renderer_B = renderer_B
        self.direction = 1 if direction >= 0 else -1
        self.slide_speed = slide_speed

        self.device_display_mode = DeviceDisplayMode.MIRRORED

        self._x_offset = 0
        self._target_offset = None
        self._sliding = True

    def is_done(self) -> bool:
        return not self._sliding

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """
        1. Lazily work out screen width / target.
        2. Advance the slide (updates self._x_offset).
        3. Ask each child renderer to draw onto its own temp surface.
        4. Blit those temps to `window` at their current offsets.
        """
        # ----------------------------------------------------------------- #
        # lazy-init measurements
        # ----------------------------------------------------------------- #
        if self._target_offset is None:
            self._screen_w = window.get_width()
            # A ends off-screen opposite B’s spawn edge
            self._target_offset = -self.direction * self._screen_w

        # ----------------------------------------------------------------- #
        # 1. advance the slide
        # ----------------------------------------------------------------- #
        if self._sliding:
            dist = self._target_offset - self._x_offset
            step_size = (
                dist
                if abs(dist) <= self.slide_speed          # snap on final frame
                else self.slide_speed * (1 if dist > 0 else -1)
            )
            self._x_offset += step_size
            if self._x_offset <= self._target_offset:
                self._sliding = False    

        # ----------------------------------------------------------------- #
        # 2. render both children to off-screen surfaces
        # ----------------------------------------------------------------- #
        size = window.get_size()
        surf_A = pygame.Surface(size, pygame.SRCALPHA)
        surf_B = pygame.Surface(size, pygame.SRCALPHA)

        result_A = self.renderer_A._internal_process(
            surf_A, clock, peripheral_manager, orientation
        )
        result = self.renderer_B._internal_process(
            surf_B, clock, peripheral_manager, orientation
        )

        # ----------------------------------------------------------------- #
        # 3. blit at their current offsets
        #    A : starts 0 → slides to ±screen_w
        #    B : starts ±screen_w → slides to 0
        # ----------------------------------------------------------------- #
        offset_A = (self._x_offset, 0)
        offset_B = (self._x_offset + self.direction * self._screen_w, 0)

        # Just draw a pink screen
        # surf_A.fill((255, 0, 255))
        window.blit(surf_A, offset_A)
        window.blit(surf_B, offset_B)