"""Tests for compass smoothing behaviour."""

from __future__ import annotations

from heart.peripheral.compass import Compass
from heart.peripheral.core import Input


class TestCompassSmoothing:
    """Validate compass smoothing outputs to keep navigation data stable."""

    def test_window_smoothing_tracks_recent_samples(self) -> None:
        """Confirm the windowed mean uses recent samples to prevent stale headings."""

        compass = Compass(window_size=2, smoothing_mode="window")
        compass._handle_magnetometer(
            Input(event_type="peripheral.magnetometer.vector", data={"x": 1, "y": 2, "z": 3})
        )
        compass._handle_magnetometer(
            Input(event_type="peripheral.magnetometer.vector", data={"x": 3, "y": 4, "z": 5})
        )
        compass._handle_magnetometer(
            Input(event_type="peripheral.magnetometer.vector", data={"x": 5, "y": 6, "z": 7})
        )

        assert compass.get_average_vector() == (4.0, 5.0, 6.0)

    def test_ema_smoothing_blends_samples(self) -> None:
        """Ensure EMA smoothing blends inputs for responsive yet stable heading updates."""

        compass = Compass(smoothing_mode="ema", ema_alpha=0.5)
        compass._handle_magnetometer(
            Input(event_type="peripheral.magnetometer.vector", data={"x": 2, "y": 4, "z": 6})
        )
        compass._handle_magnetometer(
            Input(event_type="peripheral.magnetometer.vector", data={"x": 6, "y": 8, "z": 10})
        )

        assert compass.get_average_vector() == (4.0, 6.0, 8.0)
