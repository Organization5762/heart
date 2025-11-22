import pytest

from heart.events.types import MagnetometerVector
from heart.peripheral.compass import Compass


class TestPeripheralCompass:
    """Group Peripheral Compass tests so peripheral compass behaviour stays reliable. This preserves confidence in peripheral compass for end-to-end scenarios."""

    def test_compass_tracks_latest_vector(self) -> None:
        """Verify that Compass stores the latest magnetometer vector emitted. This ensures heading queries always reflect the most recent sensor input."""
        compass = Compass(window_size=3)

        MagnetometerVector(x=12.0, y=-5.0, z=1.5)

        # TODO: Needs an "add event" or something to sensors
        # emit(sample.to_input(producer_id=0))

        vector = compass.get_latest_vector()
        assert vector is not None
        assert vector[0] == pytest.approx(12.0)
        assert vector[1] == pytest.approx(-5.0)
        assert vector[2] == pytest.approx(1.5)



    def test_compass_heading_uses_smoothed_average(self) -> None:
        """Verify that Compass computes heading degrees from a smoothed average of recent vectors. This stabilises navigation so jittery measurements do not cause erratic bearings."""
        compass = Compass(window_size=2)

        # _emit_vector(MagnetometerVector(x=0.0, y=1.0, z=0.0))
        assert compass.get_heading_degrees() == pytest.approx(0.0)

        # _emit_vector(MagnetometerVector(x=1.0, y=0.0, z=0.0))
        assert compass.get_heading_degrees() == pytest.approx(45.0)



    def test_compass_returns_none_for_empty_or_zero_vectors(self) -> None:
        """Verify that Compass returns None when no meaningful magnetometer samples are available. This guards downstream logic from acting on invalid sensor data."""
        compass = Compass(window_size=4)

        assert compass.get_heading_degrees() is None
        assert compass.get_average_vector() is None

        # _emit_vector(MagnetometerVector(x=0.0, y=0.0, z=0.0))

        assert compass.get_heading_degrees() is None
