from __future__ import annotations

import math

from heart.firmware_io import constants
from heart.peripheral.compass import Compass, MagneticField
from heart.peripheral.core.event_bus import EventBus


def emit_sample(compass: Compass, x: float, y: float, z: float) -> None:
    compass.update_due_to_data(
        {"event_type": constants.MAGNETIC, "data": {"x": x, "y": y, "z": z}}
    )


def test_heading_zero_degrees() -> None:
    compass = Compass(smoothing_window=1)
    emit_sample(compass, 1.0, 0.0, 0.0)

    heading = compass.get_heading_degrees()
    assert heading is not None
    assert math.isclose(heading, 0.0, abs_tol=1e-6)


def test_heading_quadrants() -> None:
    compass = Compass(smoothing_window=1)
    emit_sample(compass, 0.0, 1.0, 0.0)
    heading = compass.get_heading_degrees()
    assert heading is not None
    assert math.isclose(heading, 90.0, abs_tol=1e-6)

    emit_sample(compass, -1.0, 0.0, 0.0)
    heading = compass.get_heading_degrees()
    assert heading is not None
    assert math.isclose(heading, 180.0, abs_tol=1e-6)

    emit_sample(compass, 0.0, -1.0, 0.0)
    heading = compass.get_heading_degrees()
    assert heading is not None
    assert math.isclose(heading, 270.0, abs_tol=1e-6)


def test_heading_smoothing() -> None:
    compass = Compass(smoothing_window=2)
    emit_sample(compass, 1.0, 0.0, 0.0)
    emit_sample(compass, 0.0, 1.0, 0.0)
    heading = compass.get_heading_degrees()
    assert heading is not None
    assert math.isclose(heading, 45.0, abs_tol=1e-6)


def test_event_bus_subscription() -> None:
    compass = Compass(smoothing_window=3)
    bus = EventBus()
    compass.attach_event_bus(bus)

    bus.emit(constants.MAGNETIC, {"x": 1.0, "y": 2.0, "z": 3.0})

    latest = compass.get_latest_vector()
    assert latest == MagneticField(1.0, 2.0, 3.0)

    smoothed = compass.get_smoothed_vector()
    assert smoothed == MagneticField(1.0, 2.0, 3.0)


def test_invalid_payloads_are_ignored() -> None:
    compass = Compass()
    compass.update_due_to_data({"event_type": constants.MAGNETIC, "data": None})
    assert compass.get_latest_vector() is None

    compass.update_due_to_data({"event_type": constants.MAGNETIC, "data": {"x": 1}})
    assert compass.get_latest_vector() is None
