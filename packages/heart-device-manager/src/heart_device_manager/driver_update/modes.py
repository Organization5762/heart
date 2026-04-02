"""Mode selection for driver update workflows."""

from enum import StrEnum


class UpdateMode(StrEnum):
    """Supported driver update strategies."""

    AUTO = "auto"
    ARDUINO = "arduino"
    CIRCUITPYTHON = "circuitpython"
