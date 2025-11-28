import pytest

from heart.events.types import AccelerometerVector, MagnetometerVector
from heart.peripheral.sensor import Accelerometer


class TestPeripheralAccelerometerEvent:
    """Group Peripheral Accelerometer Event Bus tests so peripheral accelerometer event bus behaviour stays reliable. This preserves confidence in peripheral accelerometer event bus for end-to-end scenarios."""

    @pytest.mark.parametrize("event_type", ["acceleration", "sensor.acceleration"])
    def test_accelerometer_emits_vector(self, event_type: str) -> None:
        """Verify that Accelerometer publishes acceleration vectors. This ensures motion data reaches subscribers that drive orientation and gesture features."""
        captured: list[AccelerometerVector] = []

        def _capture(event):
            captured.append(
                AccelerometerVector(
                    x=event.data["x"], y=event.data["y"], z=event.data["z"]
                )
            )

        # TODO: Refactor
        # subscribe(AccelerometerVector.EVENT_TYPE, _capture)
        accel = Accelerometer(port="/dev/null", baudrate=9600)

        accel._update_due_to_data(
            {"event_type": event_type, "data": {"x": 1.0, "y": -2.5, "z": 0.5}}
        )

        assert captured
        vector = captured[0]
        assert vector.x == pytest.approx(1.0)
        assert vector.y == pytest.approx(-2.5)
        assert vector.z == pytest.approx(0.5)



    def test_accelerometer_emits_magnetometer_vector(self) -> None:
        """Verify that Accelerometer publishes magnetometer vectors. This supports heading calculations that depend on magnetometer updates."""
        captured: list[MagnetometerVector] = []

        def _capture(event):
            captured.append(
                MagnetometerVector(
                    x=event.data["x"], y=event.data["y"], z=event.data["z"]
                )
            )

        # TODO: Refactor
        # subscribe(MagnetometerVector.EVENT_TYPE, _capture)
        accel = Accelerometer(port="/dev/null", baudrate=9600)

        accel._update_due_to_data(
            {"event_type": "sensor.magnetic", "data": {"x": -30.0, "y": 12.0, "z": 4.0}}
        )

        assert captured
        vector = captured[0]
        assert vector.x == pytest.approx(-30.0)
        assert vector.y == pytest.approx(12.0)
        assert vector.z == pytest.approx(4.0)
