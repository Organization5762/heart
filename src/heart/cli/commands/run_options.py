import os
from pathlib import Path

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIGURATION = "lib_2025"
CONFIGURATION_OVERRIDE_ENV_VAR = "HEART_RUN_CONFIGURATION"
DEFAULT_ADD_LOW_POWER_MODE = True
DEFAULT_WITH_BEATS = False
DEFAULT_INSTALL_BEATS_DEPS = True
DEFAULT_BEATS_WORKSPACE = Path("experimental/beats")


def resolve_configuration_name(configuration: str) -> str:
    """Return the requested configuration after applying any environment override."""

    override = os.environ.get(CONFIGURATION_OVERRIDE_ENV_VAR, "").strip()
    if not override:
        return configuration
    if override != configuration:
        logger.info(
            "Using configuration override from %s: %s",
            CONFIGURATION_OVERRIDE_ENV_VAR,
            override,
        )
    return override
