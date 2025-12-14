from __future__ import annotations

from dataclasses import dataclass, replace

from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class SlideTransitionState:
    peripheral_manager: PeripheralManager
    x_offset: int = 0
    target_offset: int | None = None
    sliding: bool = True
    screen_w: int = 0

    def with_screen_width(
        self, screen_w: int, direction: int
    ) -> "SlideTransitionState":
        if self.target_offset is None or self.screen_w != screen_w:
            return replace(self, screen_w=screen_w, target_offset=-direction * screen_w)
        return self

    def advance(self, *, direction: int, slide_speed: int) -> "SlideTransitionState":
        if not self.sliding or self.target_offset is None:
            return self

        dist = self.target_offset - self.x_offset
        step_size = (
            dist
            if abs(dist) <= slide_speed
            else slide_speed * (1 if dist > 0 else -1)
        )
        new_offset = self.x_offset + step_size
        still_sliding = True

        if (direction > 0 and new_offset <= self.target_offset) or (
            direction < 0 and new_offset >= self.target_offset
        ):
            new_offset = self.target_offset
            still_sliding = False

        return replace(self, x_offset=new_offset, sliding=still_sliding)
