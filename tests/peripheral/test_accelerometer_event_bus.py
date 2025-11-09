import pytest

from heart.events.types import AccelerometerVector, MagnetometerVector
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.sensor import Accelerometer


@pytest.mark.parametrize("event_type", ["acceleration", "sensor.acceleration"])
def test_accelerometer_emits_vector(event_type: str) -> None:
    bus = EventBus()
    captured: list[AccelerometerVector] = []

    def _capture(event):
        captured.append(
            AccelerometerVector(
                x=event.data["x"], y=event.data["y"], z=event.data["z"]
            )
        )

    bus.subscribe(AccelerometerVector.EVENT_TYPE, _capture)
    accel = Accelerometer(port="/dev/null", baudrate=9600, event_bus=bus, producer_id=7)

    accel._update_due_to_data(
        {"event_type": event_type, "data": {"x": 1.0, "y": -2.5, "z": 0.5}}
    )

    assert captured
    vector = captured[0]
    assert vector.x == pytest.approx(1.0)
    assert vector.y == pytest.approx(-2.5)
    assert vector.z == pytest.approx(0.5)


def test_accelerometer_emits_magnetometer_vector() -> None:
    bus = EventBus()
    captured: list[MagnetometerVector] = []

    def _capture(event):
        captured.append(
            MagnetometerVector(
                x=event.data["x"], y=event.data["y"], z=event.data["z"]
            )
        )

    bus.subscribe(MagnetometerVector.EVENT_TYPE, _capture)
    accel = Accelerometer(port="/dev/null", baudrate=9600, event_bus=bus, producer_id=7)

    accel._update_due_to_data(
        {"event_type": "sensor.magnetic", "data": {"x": -30.0, "y": 12.0, "z": 4.0}}
    )

    assert captured
    vector = captured[0]
    assert vector.x == pytest.approx(-30.0)
    assert vector.y == pytest.approx(12.0)
    assert vector.z == pytest.approx(4.0)
