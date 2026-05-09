from __future__ import annotations

import pytest
from openant.base.driver import DriverNotFound

import heart.peripheral.heart_rates as heart_rates
from heart.peripheral.heart_rates import HeartRateManager


class _DriverlessNode:
    """Raise the same ANT error a developer workstation hits without hardware support."""

    def __init__(self) -> None:
        raise DriverNotFound


class TestHeartRateManagerDetection:
    """Verify heart-rate detection degrades gracefully so local startup does not depend on optional ANT hardware."""

    def test_detect_skips_when_ant_driver_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify missing ANT drivers produce no peripherals so macOS developers can boot the runtime without optional heart-rate hardware."""
        monkeypatch.setattr(heart_rates, "Node", _DriverlessNode)

        detected = list(HeartRateManager.detect())

        assert detected == []
