import pytest

from heart.events.types import MagnetometerVector
from heart.peripheral.compass import Compass
from heart.peripheral.core.event_bus import EventBus


def _emit_vector(bus: EventBus, vector: MagnetometerVector) -> None:
    bus.emit(vector.to_input(producer_id=0))


def test_compass_tracks_latest_vector() -> None:
    bus = EventBus()
    compass = Compass(window_size=3)
    compass.attach_event_bus(bus)

    sample = MagnetometerVector(x=12.0, y=-5.0, z=1.5)
    _emit_vector(bus, sample)

    vector = compass.get_latest_vector()
    assert vector is not None
    assert vector[0] == pytest.approx(12.0)
    assert vector[1] == pytest.approx(-5.0)
    assert vector[2] == pytest.approx(1.5)


def test_compass_heading_uses_smoothed_average() -> None:
    bus = EventBus()
    compass = Compass(window_size=2)
    compass.attach_event_bus(bus)

    _emit_vector(bus, MagnetometerVector(x=0.0, y=1.0, z=0.0))
    assert compass.get_heading_degrees() == pytest.approx(0.0)

    _emit_vector(bus, MagnetometerVector(x=1.0, y=0.0, z=0.0))
    assert compass.get_heading_degrees() == pytest.approx(45.0)


def test_compass_returns_none_for_empty_or_zero_vectors() -> None:
    compass = Compass(window_size=4)

    assert compass.get_heading_degrees() is None
    assert compass.get_average_vector() is None

    bus = EventBus()
    compass.attach_event_bus(bus)
    _emit_vector(bus, MagnetometerVector(x=0.0, y=0.0, z=0.0))

    assert compass.get_heading_degrees() is None
