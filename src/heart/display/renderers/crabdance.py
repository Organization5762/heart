from __future__ import annotations

import math

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.display.renderers.spritesheet import LoopPhase, SpritesheetLoop
from heart.peripheral.manager import PeripheralManager

BASE_BG = (4, 3, 10)
MAGENTA = (255, 50, 180)
CYAN = (40, 255, 240)
BLUE = (70, 110, 255)
WHITE = (255, 255, 255)
MIN_DURATION_SCALE = -0.6
MAX_DURATION_SCALE = 0.6


class CrabDanceLaserBackground(BaseRenderer):
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        elapsed = pygame.time.get_ticks() / 1000.0
        width, height = window.get_size()
        window.fill(BASE_BG)
        self._draw_gradient(window, width, height, elapsed)
        self._draw_laser_fan(window, width, height, elapsed, side="left")
        self._draw_laser_fan(window, width, height, elapsed + 0.35, side="right")
        self._draw_strobe(window, width, height, elapsed)
        self._draw_floor_glow(window, width, height, elapsed)

    def _draw_gradient(
        self, window: pygame.Surface, width: int, height: int, elapsed: float
    ) -> None:
        pulse = 0.5 + 0.5 * math.sin(elapsed * 2.2)
        for y in range(height):
            blend = y / max(height - 1, 1)
            color = (
                int(BASE_BG[0] * (1 - blend) + 18 * pulse * blend),
                int(BASE_BG[1] * (1 - blend) + 8 * blend),
                int(BASE_BG[2] * (1 - blend) + 42 * blend),
            )
            pygame.draw.line(window, color, (0, y), (width, y))

    def _draw_laser_fan(
        self,
        window: pygame.Surface,
        width: int,
        height: int,
        elapsed: float,
        *,
        side: str,
    ) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        origin = (4, height - 2) if side == "left" else (width - 4, height - 2)
        beam_count = 5
        base_angle = -0.95 if side == "left" else -2.2
        sweep = math.sin(elapsed * 2.8) * 0.4
        colors = [MAGENTA, CYAN, BLUE, CYAN, MAGENTA]

        for idx in range(beam_count):
            t = idx / max(beam_count - 1, 1)
            angle = base_angle + sweep + ((t - 0.5) * 0.9)
            length = int(height * 1.15)
            end_x = int(origin[0] + math.cos(angle) * length)
            end_y = int(origin[1] + math.sin(angle) * length)
            alpha = 85 + int(60 * (0.5 + 0.5 * math.sin(elapsed * 7.0 + idx)))
            color = (*colors[idx], alpha)
            pygame.draw.line(overlay, color, origin, (end_x, end_y), 2)
            pygame.draw.line(
                overlay,
                (*WHITE, min(alpha // 2, 90)),
                origin,
                (end_x, end_y),
                1,
            )

        window.blit(overlay, (0, 0))

    def _draw_strobe(
        self, window: pygame.Surface, width: int, height: int, elapsed: float
    ) -> None:
        if math.sin(elapsed * 8.5) > 0.88:
            flash = pygame.Surface((width, height), pygame.SRCALPHA)
            flash.fill((255, 255, 255, 38))
            window.blit(flash, (0, 0))

    def _draw_floor_glow(
        self, window: pygame.Surface, width: int, height: int, elapsed: float
    ) -> None:
        floor = pygame.Surface((width, height), pygame.SRCALPHA)
        glow = 40 + int(25 * (0.5 + 0.5 * math.sin(elapsed * 4.0)))
        pygame.draw.ellipse(
            floor,
            (*MAGENTA, glow),
            pygame.Rect(width // 8, height - 8, (width * 3) // 4, 6),
        )
        for x in range(0, width, 4):
            alpha = 18 + int(12 * (0.5 + 0.5 * math.sin(elapsed * 5.0 + x)))
            pygame.draw.line(
                floor,
                (*CYAN, alpha),
                (x, height - 8),
                (x + 2, height),
                1,
            )
        window.blit(floor, (0, 0))


class ControlledCrabDance(SpritesheetLoop):
    """Crabdance spritesheet with clamped speed control."""

    def __init__(
        self,
        *,
        image_scale: float,
        offset_y: int,
    ) -> None:
        super().__init__(
            sheet_file_path="crab_dance.png",
            metadata_file_path="crab_dance.json",
            image_scale=image_scale,
            offset_y=offset_y,
            disable_input=False,
        )
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def __duration_scale_factor(self, peripheral_manager: PeripheralManager) -> float:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        raw = current_value / 12.0
        return max(MIN_DURATION_SCALE, min(MAX_DURATION_SCALE, raw))

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        screen_width, screen_height = window.get_size()
        current_kf = self.frames[self.phase][self.current_frame]
        if self.disable_input:
            kf_duration = current_kf.duration
        else:
            duration_scale = self.__duration_scale_factor(peripheral_manager)
            kf_duration = max(1, current_kf.duration * (1 - duration_scale))

        if self.time_since_last_update is None or self.time_since_last_update > kf_duration:
            if not self.initialized:
                self._initialize()
            if self._should_calibrate:
                self._calibrate(peripheral_manager)
            else:
                self.current_frame += 1
                self.time_since_last_update = 0
                if self.current_frame >= len(self.frames[self.phase]):
                    self.current_frame = 0
                    match self.phase:
                        case LoopPhase.START:
                            self.phase = LoopPhase.LOOP
                        case LoopPhase.LOOP:
                            if self.loop_count < 4:
                                self.loop_count += 1
                            else:
                                self.loop_count = 0
                                if len(self.frames[LoopPhase.END]) > 0:
                                    self.phase = LoopPhase.END
                                elif len(self.frames[LoopPhase.START]) > 0:
                                    self.phase = LoopPhase.START
                        case LoopPhase.END:
                            self.phase = LoopPhase.START

        image = self.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image,
            (int(screen_width * self.image_scale), int(screen_height * self.image_scale)),
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2
        window.blit(scaled, (center_x + self.offset_x, center_y + self.offset_y))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
