from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class SlideTransitionState:
    x_offset: int = 0
    target_offset: int | None = None
    sliding: bool = True
    screen_w: int = 0


class SlideTransitionRenderer(AtomicBaseRenderer[SlideTransitionState]):
    """Slides renderer_B into view while renderer_A moves out.

    direction  =  1  → B comes from the right  (A → left) direction  = -1  → B comes
    from the left   (A → right)

    """

    def __init__(
        self,
        renderer_A: BaseRenderer,
        renderer_B: BaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 10,
    ) -> None:
        self.renderer_A = renderer_A
        self.renderer_B = renderer_B
        self.direction = 1 if direction >= 0 else -1
        self.slide_speed = slide_speed  # Use the parameter value instead of hardcoding

        self.device_display_mode = DeviceDisplayMode.MIRRORED
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(self) -> SlideTransitionState:
        return SlideTransitionState()

    def is_done(self) -> bool:
        return not self.state.sliding

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """
        1. Lazily work out screen width / target.
        2. Advance the slide (updates the atomic state offset).
        3. Ask each child renderer to draw onto its own temp surface.
        4. Blit those temps to `window` at their current offsets.
        """
        # ----------------------------------------------------------------- #
        # lazy-init measurements
        # ----------------------------------------------------------------- #
        state = self.state

        screen_w = window.get_width()
        if state.target_offset is None or state.screen_w != screen_w:
            target_offset = -self.direction * screen_w
            self.update_state(
                target_offset=target_offset,
                screen_w=screen_w,
            )
            state = self.state

        # ----------------------------------------------------------------- #
        # 1. advance the slide
        # ----------------------------------------------------------------- #
        if state.sliding and state.target_offset is not None:
            dist = state.target_offset - state.x_offset
            step_size = (
                dist
                if abs(dist) <= self.slide_speed  # snap on final frame
                else self.slide_speed * (1 if dist > 0 else -1)
            )
            new_offset = state.x_offset + step_size
            still_sliding = True

            # Check if we've reached or passed the target in either direction
            if (self.direction > 0 and new_offset <= state.target_offset) or (
                self.direction < 0 and new_offset >= state.target_offset
            ):
                new_offset = state.target_offset
                still_sliding = False

            self.update_state(x_offset=new_offset, sliding=still_sliding)
            state = self.state

        # ----------------------------------------------------------------- #
        # 2. render both children to off-screen surfaces
        # ----------------------------------------------------------------- #
        size = window.get_size()
        surf_A = pygame.Surface(size, pygame.SRCALPHA)
        surf_B = pygame.Surface(size, pygame.SRCALPHA)

        self.renderer_A._internal_process(
            surf_A, clock, peripheral_manager, Rectangle.with_layout(1, 1)
        )
        self.renderer_B._internal_process(
            surf_B, clock, peripheral_manager, Rectangle.with_layout(1, 1)
        )

        # ----------------------------------------------------------------- #
        # 3. blit at their current offsets
        #    A : starts 0 → slides to ±screen_w
        #    B : starts ±screen_w → slides to 0
        # ----------------------------------------------------------------- #
        offset_A = (state.x_offset, 0)
        offset_B = (state.x_offset + self.direction * state.screen_w, 0)

        # Draw the renderers at their current positions
        window.blit(surf_A, offset_A)
        window.blit(surf_B, offset_B)
