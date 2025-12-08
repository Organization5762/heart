import logging
import platform
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Literal, cast

import pygame
from PIL import Image

from heart.device import Device

logger = logging.getLogger(__name__)


class ResolutionDetectionError(RuntimeError):
    """Raised when a display resolution provider cannot parse its output."""


class DisplayResolutionProvider(ABC):
    """Base class for retrieving the active display resolution."""

    DEFAULT_RESOLUTION: tuple[int, int, float] = (1920, 1080, 16 / 9)

    def get_resolution(self) -> tuple[int, int, float]:
        try:
            return self._detect_resolution()
        except ResolutionDetectionError as error:
            logger.warning(str(error))
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            logger.warning(self._command_failure_message(error))
        return self.DEFAULT_RESOLUTION

    @abstractmethod
    def _detect_resolution(self) -> tuple[int, int, float]:
        """Return the detected display resolution."""

    def _command_failure_message(self, error: Exception) -> str:
        return f"Could not detect display resolution: {error}. Using default resolution."


class MacDisplayResolutionProvider(DisplayResolutionProvider):
    """Detect the active display resolution on macOS hosts."""

    def _detect_resolution(self) -> tuple[int, int, float]:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            if "Resolution" in line:
                res = line.split(":")[1].strip()
                parsable = res.replace(" x ", "x").split(" ")[0]
                width, height = map(int, parsable.split("x"))
                aspect_ratio = width / height
                logger.info(f"Detected macOS display resolution: {width}x{height}")
                return width, height, aspect_ratio

        raise ResolutionDetectionError(
            "Could not parse display resolution from system_profiler output."
        )

    def _command_failure_message(self, error: Exception) -> str:
        return f"Could not run system_profiler: {error}. Using default resolution."


class XrandrDisplayResolutionProvider(DisplayResolutionProvider):
    """Detect the active display resolution via xrandr output."""

    def _detect_resolution(self) -> tuple[int, int, float]:
        result = subprocess.run(
            ["xrandr", "--query"], capture_output=True, text=True, check=True
        )

        for line in result.stdout.splitlines():
            if " current " in line:
                res = line.split(" current ")[1].split(",")[0].strip()
                width, height = map(int, res.split("x"))
                aspect_ratio = width / height
                logger.info(f"Detected Linux/X11 display resolution: {width}x{height}")
                return width, height, aspect_ratio

        raise ResolutionDetectionError(
            "Could not parse display resolution from xrandr output."
        )

    def _command_failure_message(self, error: Exception) -> str:
        return f"Could not run xrandr: {error}. Using default resolution."


class FallbackDisplayResolutionProvider(DisplayResolutionProvider):
    """Fallback provider when no platform specific implementation exists."""

    def get_resolution(self) -> tuple[int, int, float]:
        logger.info("Display resolution detection not supported. Using default resolution.")
        return self.DEFAULT_RESOLUTION

    def _detect_resolution(self) -> tuple[int, int, float]:
        return self.DEFAULT_RESOLUTION


def _display_resolution_provider() -> DisplayResolutionProvider:
    system = platform.system()
    if system == "Darwin":
        return MacDisplayResolutionProvider()
    if system == "Linux":
        return XrandrDisplayResolutionProvider()
    return FallbackDisplayResolutionProvider()


@lru_cache(maxsize=1)
def get_display_resolution() -> tuple[int, int, float]:
    return _display_resolution_provider().get_resolution()


@dataclass
class LocalScreen(Device):
    width: int
    height: int

    def __post_init__(self) -> None:
        self.scaled_screen = pygame.display.set_mode(
            (
                self.full_display_size()[0] * self.scale_factor,
                self.full_display_size()[1] * self.scale_factor,
            ),
            pygame.SHOWN,
        )

    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @cached_property
    def scale_factor(self) -> int:
        width, height, _ = get_display_resolution()
        current_width, current_height = self.full_display_size()

        result = max(min(width // current_width, height // current_height), 1)
        return max(result // 3, 1)

    def set_image(self, image: Image.Image) -> None:
        assert image.size == self.full_display_size(), (
            f"Image size does not match display size. Image size: {image.size}, Display size: {self.full_display_size()}"
        )

        scaled_image = image.resize(
            (
                self.full_display_size()[0] * self.scale_factor,
                self.full_display_size()[1] * self.scale_factor,
            )
        )

        self.scaled_screen.blit(
            pygame.image.fromstring(
                scaled_image.tobytes(),
                scaled_image.size,
                _normalize_surface_mode(scaled_image.mode),
            ),
            (0, 0),
        )


_SURFACE_MODES = {
    "P",
    "RGB",
    "RGBX",
    "RGBA",
    "ARGB",
    "BGRA",
}


def _normalize_surface_mode(mode: str) -> Literal["P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA"]:
    if mode not in _SURFACE_MODES:
        raise ValueError(f"Unsupported image mode for pygame surface: {mode}")
    return cast(Literal["P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA"], mode)

