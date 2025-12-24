import logging
import platform
import subprocess
from abc import ABC, abstractmethod
from functools import lru_cache

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
            logger.warning("%s", error)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            logger.warning("%s", self._command_failure_message(error))
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
                logger.info(
                    "Detected macOS display resolution: %sx%s",
                    width,
                    height,
                )
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
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            if " current " in line:
                res = line.split(" current ")[1].split(",")[0].strip()
                width, height = map(int, res.split("x"))
                aspect_ratio = width / height
                logger.info(
                    "Detected Linux/X11 display resolution: %sx%s",
                    width,
                    height,
                )
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
