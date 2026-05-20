from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

FLOATING_EMOJI_POOP = "poop"
FLOATING_EMOJI_SKULL = "skull"
FLOATING_EMOJI_HEART = "heart"
FLOATING_EMOJI_STAR = "star"
FLOATING_EMOJI_RAINBOW = "rainbow"
FLOATING_FACE_NAMES = (
    "seb",
    "faye",
    "will",
    "clem",
    "cal",
    "sri",
    "lampe",
    "ditto",
)
SUPPORTED_FLOATING_EMOJIS = frozenset(
    {
        FLOATING_EMOJI_POOP,
        FLOATING_EMOJI_SKULL,
        FLOATING_EMOJI_HEART,
        FLOATING_EMOJI_STAR,
        FLOATING_EMOJI_RAINBOW,
        *FLOATING_FACE_NAMES,
    }
)
FLOATING_EMOJI_DURATION_SECONDS = 3.2
FLOATING_EMOJI_MAX_PARTICLES_PER_SCREEN = 5


@dataclass(frozen=True)
class FloatingEmojiOverlayState:
    width: int
    height: int
    columns: int
    rows: int


@dataclass(frozen=True)
class FloatingEmojiParticle:
    emoji: str
    born_at: float
    x: float
    size: int
    drift_pixels: float
    duration_seconds: float = FLOATING_EMOJI_DURATION_SECONDS


class FloatingEmojiOverlayRenderer(StatefulBaseRenderer[FloatingEmojiOverlayState]):
    def __init__(
        self,
        *,
        now: Callable[[], float] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._now = now or time.monotonic
        self._rng = rng or random.Random()
        self._particles: list[FloatingEmojiParticle] = []
        self._avatar_images: dict[str, pygame.Surface | None] = {}

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FloatingEmojiOverlayState:
        width, height = window.get_size()
        return FloatingEmojiOverlayState(
            width=width,
            height=height,
            columns=max(1, orientation.layout.columns),
            rows=max(1, orientation.layout.rows),
        )

    def spawn(self, emoji: str) -> None:
        if emoji not in SUPPORTED_FLOATING_EMOJIS:
            raise ValueError(f"Unsupported floating emoji: {emoji}")

        now = self._now()
        width = self.state.width if self.initialized else 256
        height = self.state.height if self.initialized else 64
        size = max(14, min(42, int(height * 0.54)))
        margin = size * 0.65
        x = self._rng.uniform(margin, max(margin, width - margin))
        particle = FloatingEmojiParticle(
            emoji=emoji,
            born_at=now,
            x=x,
            size=size,
            drift_pixels=self._rng.uniform(-size * 0.65, size * 0.65),
        )
        self._particles.append(particle)
        self._enforce_screen_particle_limit(particle.x)

    def has_active_emojis(self) -> bool:
        self._drop_expired_particles(self._now())
        return bool(self._particles)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            return

        width, height = window.get_size()
        columns = max(1, orientation.layout.columns)
        rows = max(1, orientation.layout.rows)
        if (width, height, columns, rows) != (
            self.state.width,
            self.state.height,
            self.state.columns,
            self.state.rows,
        ):
            self.set_state(
                FloatingEmojiOverlayState(
                    width=width,
                    height=height,
                    columns=columns,
                    rows=rows,
                )
            )

        window.screen.fill((0, 0, 0, 0))
        now = self._now()
        self._drop_expired_particles(now)
        for particle in self._particles:
            self._draw_particle(window.screen, particle, now)

    def _drop_expired_particles(self, now: float) -> None:
        self._particles = [
            particle
            for particle in self._particles
            if now - particle.born_at < particle.duration_seconds
        ]

    def _enforce_screen_particle_limit(self, x: float) -> None:
        screen_index = self._screen_index_for_x(x)
        particles_on_screen = [
            particle
            for particle in self._particles
            if self._screen_index_for_x(particle.x) == screen_index
        ]
        overflow = len(particles_on_screen) - FLOATING_EMOJI_MAX_PARTICLES_PER_SCREEN
        if overflow <= 0:
            return

        ids_to_drop = {
            id(particle)
            for particle in sorted(
                particles_on_screen,
                key=lambda particle: particle.born_at,
            )[:overflow]
        }
        self._particles = [
            particle for particle in self._particles if id(particle) not in ids_to_drop
        ]

    def _screen_index_for_x(self, x: float) -> int:
        column_width = max(1.0, self.state.width / self.state.columns)
        column = int(max(0, min(self.state.columns - 1, x // column_width)))
        return column

    def _draw_particle(
        self,
        screen: pygame.Surface,
        particle: FloatingEmojiParticle,
        now: float,
    ) -> None:
        progress = max(
            0.0,
            min(1.0, (now - particle.born_at) / particle.duration_seconds),
        )
        _, height = screen.get_size()
        wobble = math.sin(progress * math.tau * 1.7) * particle.size * 0.12
        x = particle.x + particle.drift_pixels * progress + wobble
        y = (height - particle.size * 0.52) - progress * (height + particle.size * 0.9)
        alpha = 255 if progress < 0.78 else int(255 * (1.0 - progress) / 0.22)
        icon = pygame.Surface((particle.size, particle.size), pygame.SRCALPHA)
        self._draw_icon(icon, particle.emoji)
        icon.set_alpha(max(0, min(255, alpha)))
        screen.blit(icon, (round(x - particle.size / 2), round(y - particle.size / 2)))

    def _draw_icon(self, surface: pygame.Surface, emoji: str) -> None:
        if emoji in FLOATING_FACE_NAMES:
            self._draw_avatar_icon(surface, emoji)
            return
        _draw_emoji_icon(surface, emoji)

    def _draw_avatar_icon(self, surface: pygame.Surface, name: str) -> None:
        avatar = self._load_avatar(name)
        if avatar is None:
            _draw_face_placeholder(surface, name)
            return

        size = surface.get_width()
        image_size = max(1, round(size * 0.88))
        scaled = pygame.transform.scale(avatar, (image_size, image_size))
        rect = scaled.get_rect(center=(size // 2, size // 2))
        pygame.draw.circle(
            surface,
            (255, 255, 255, 230),
            (size // 2, size // 2),
            round(size * 0.48),
        )
        pygame.draw.circle(
            surface,
            (20, 25, 30, 230),
            (size // 2, size // 2),
            round(size * 0.43),
        )
        surface.blit(scaled, rect)

    def _load_avatar(self, name: str) -> pygame.Surface | None:
        if name in self._avatar_images:
            return self._avatar_images[name]
        try:
            avatar = Loader.load(f"avatars/{name}_32.png")
        except Exception:
            avatar = None
        self._avatar_images[name] = avatar
        return avatar


def _draw_emoji_icon(surface: pygame.Surface, emoji: str) -> None:
    if emoji == FLOATING_EMOJI_HEART:
        _draw_heart(surface)
    elif emoji == FLOATING_EMOJI_STAR:
        _draw_star(surface)
    elif emoji == FLOATING_EMOJI_RAINBOW:
        _draw_rainbow(surface)
    elif emoji == FLOATING_EMOJI_SKULL:
        _draw_skull(surface)
    elif emoji == FLOATING_EMOJI_POOP:
        _draw_poop(surface)


def _draw_heart(surface: pygame.Surface) -> None:
    size = surface.get_width()
    points = [
        (size * 0.50, size * 0.86),
        (size * 0.16, size * 0.54),
        (size * 0.10, size * 0.30),
        (size * 0.26, size * 0.14),
        (size * 0.43, size * 0.22),
        (size * 0.50, size * 0.34),
        (size * 0.57, size * 0.22),
        (size * 0.74, size * 0.14),
        (size * 0.90, size * 0.30),
        (size * 0.84, size * 0.54),
    ]
    pygame.draw.polygon(surface, (80, 0, 20, 220), points)
    pygame.draw.polygon(surface, (255, 45, 92, 255), points)
    pygame.draw.circle(
        surface,
        (255, 94, 132, 255),
        (round(size * 0.32), round(size * 0.34)),
        round(size * 0.19),
    )
    pygame.draw.circle(
        surface,
        (255, 94, 132, 255),
        (round(size * 0.68), round(size * 0.34)),
        round(size * 0.19),
    )


def _draw_star(surface: pygame.Surface) -> None:
    size = surface.get_width()
    center = size / 2
    outer = size * 0.43
    inner = size * 0.19
    points: list[tuple[float, float]] = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append(
            (center + math.cos(angle) * radius, center + math.sin(angle) * radius)
        )
    pygame.draw.polygon(surface, (90, 58, 0, 230), points)
    pygame.draw.polygon(surface, (255, 211, 58, 255), points)
    pygame.draw.circle(
        surface,
        (255, 246, 145, 255),
        (round(size * 0.38), round(size * 0.34)),
        max(1, round(size * 0.06)),
    )


def _draw_rainbow(surface: pygame.Surface) -> None:
    size = surface.get_width()
    rect_base = size * 0.08
    colors = [
        (255, 56, 66, 255),
        (255, 140, 36, 255),
        (255, 226, 61, 255),
        (58, 216, 96, 255),
        (53, 171, 255, 255),
        (147, 95, 255, 255),
    ]
    band_width = max(2, round(size * 0.08))
    for index, color in enumerate(colors):
        inset = rect_base + index * band_width
        pygame.draw.arc(
            surface,
            color,
            (inset, inset, size - inset * 2, size - inset * 2),
            0,
            math.pi,
            band_width,
        )
    cloud_color = (244, 247, 255, 255)
    for cx, cy, radius in (
        (0.22, 0.73, 0.13),
        (0.34, 0.70, 0.16),
        (0.76, 0.73, 0.13),
        (0.64, 0.70, 0.16),
    ):
        pygame.draw.circle(
            surface,
            cloud_color,
            (round(size * cx), round(size * cy)),
            round(size * radius),
        )


def _draw_skull(surface: pygame.Surface) -> None:
    size = surface.get_width()
    ivory = (236, 238, 226, 255)
    shade = (188, 195, 188, 255)
    dark = (26, 25, 28, 255)
    pygame.draw.ellipse(
        surface, (0, 0, 0, 190), (size * 0.14, size * 0.11, size * 0.72, size * 0.66)
    )
    pygame.draw.ellipse(
        surface, ivory, (size * 0.12, size * 0.08, size * 0.76, size * 0.68)
    )
    pygame.draw.rect(
        surface,
        ivory,
        (size * 0.29, size * 0.56, size * 0.42, size * 0.27),
        border_radius=max(1, round(size * 0.08)),
    )
    pygame.draw.rect(
        surface, shade, (size * 0.32, size * 0.73, size * 0.36, size * 0.08)
    )
    pygame.draw.circle(
        surface, dark, (round(size * 0.35), round(size * 0.41)), round(size * 0.11)
    )
    pygame.draw.circle(
        surface, dark, (round(size * 0.65), round(size * 0.41)), round(size * 0.11)
    )
    pygame.draw.polygon(
        surface,
        dark,
        [
            (size * 0.50, size * 0.49),
            (size * 0.42, size * 0.62),
            (size * 0.58, size * 0.62),
        ],
    )
    for x in (0.39, 0.50, 0.61):
        pygame.draw.line(
            surface,
            dark,
            (size * x, size * 0.68),
            (size * x, size * 0.79),
            max(1, round(size * 0.04)),
        )


def _draw_poop(surface: pygame.Surface) -> None:
    size = surface.get_width()
    brown = (124, 69, 34, 255)
    light = (181, 104, 52, 255)
    dark = (54, 31, 22, 255)
    pygame.draw.ellipse(
        surface, (0, 0, 0, 170), (size * 0.13, size * 0.66, size * 0.74, size * 0.22)
    )
    pygame.draw.ellipse(
        surface, brown, (size * 0.13, size * 0.58, size * 0.74, size * 0.29)
    )
    pygame.draw.ellipse(
        surface, light, (size * 0.22, size * 0.39, size * 0.56, size * 0.31)
    )
    pygame.draw.ellipse(
        surface, brown, (size * 0.33, size * 0.23, size * 0.38, size * 0.29)
    )
    pygame.draw.polygon(
        surface,
        light,
        [
            (size * 0.50, size * 0.08),
            (size * 0.36, size * 0.31),
            (size * 0.63, size * 0.29),
        ],
    )
    pygame.draw.circle(
        surface,
        (255, 255, 255, 255),
        (round(size * 0.39), round(size * 0.57)),
        round(size * 0.07),
    )
    pygame.draw.circle(
        surface,
        (255, 255, 255, 255),
        (round(size * 0.61), round(size * 0.57)),
        round(size * 0.07),
    )
    pygame.draw.circle(
        surface,
        dark,
        (round(size * 0.40), round(size * 0.58)),
        max(1, round(size * 0.035)),
    )
    pygame.draw.circle(
        surface,
        dark,
        (round(size * 0.60), round(size * 0.58)),
        max(1, round(size * 0.035)),
    )
    pygame.draw.arc(
        surface,
        dark,
        (size * 0.39, size * 0.59, size * 0.22, size * 0.14),
        0.15,
        math.pi - 0.15,
        max(1, round(size * 0.035)),
    )


def _draw_face_placeholder(surface: pygame.Surface, name: str) -> None:
    size = surface.get_width()
    pygame.draw.circle(
        surface,
        (255, 255, 255, 230),
        (size // 2, size // 2),
        round(size * 0.48),
    )
    pygame.draw.circle(
        surface,
        (255, 105, 180, 255),
        (size // 2, size // 2),
        round(size * 0.42),
    )
    font = pygame.font.Font(None, max(12, round(size * 0.42)))
    label = font.render(name[:1].upper(), True, (16, 16, 22))
    surface.blit(label, label.get_rect(center=(size // 2, size // 2)))
