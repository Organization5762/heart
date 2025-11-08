import pytest

from heart.events.types import AccelerometerVector
from heart.peripheral.calibration import (CalibrationProfile,
                                          calibrated_virtual_peripheral)
from heart.peripheral.core.event_bus import EventBus


def test_calibration_profile_from_reference() -> None:
    profile = CalibrationProfile.from_reference(
        raw={"x": 0.12, "y": -0.08, "z": 9.6},
        expected={"x": 0.0, "y": 0.0, "z": 9.81},
        precision=3,
    )

    corrected = profile.apply({"x": 0.12, "y": -0.08, "z": 9.6})

    assert corrected == pytest.approx({"x": 0.0, "y": 0.0, "z": 9.81})


def test_calibration_profile_with_matrix_and_scale() -> None:
    profile = CalibrationProfile(
        axes=("x", "y"),
        offset=(0.0, 0.0),
        matrix=((0.0, 1.0), (-1.0, 0.0)),
        scale=(2.0, 0.5),
        precision=4,
    )

    corrected = profile.apply({"x": 1.0, "y": 2.0})

    assert corrected == pytest.approx({"x": 4.0, "y": -0.5})


def test_calibrated_virtual_peripheral_emits_corrected_event() -> None:
    bus = EventBus()
    outputs: list = []

    bus.subscribe(
        "peripheral.accelerometer.vector.calibrated",
        lambda event: outputs.append(event),
    )

    profile = CalibrationProfile.from_reference(
        raw={"x": 0.12, "y": -0.08, "z": 9.6},
        expected={"x": 0.0, "y": 0.0, "z": 9.81},
        precision=3,
    )

    definition = calibrated_virtual_peripheral(
        name="imu.calibrated",
        calibrations={
            AccelerometerVector.EVENT_TYPE: profile,
        },
        output_event_type="peripheral.accelerometer.vector.calibrated",
        output_producer_id=99,
        include_source_event=True,
        include_raw_payload=True,
    )
    bus.virtual_peripherals.register(definition)

    raw_event = AccelerometerVector(x=0.12, y=-0.08, z=9.6).to_input(producer_id=42)
    bus.emit(raw_event)

    assert len(outputs) == 1
    emitted = outputs[0]
    assert emitted.event_type == "peripheral.accelerometer.vector.calibrated"
    assert emitted.producer_id == 99
    assert emitted.data["x"] == pytest.approx(0.0)
    assert emitted.data["y"] == pytest.approx(0.0)
    assert emitted.data["z"] == pytest.approx(9.81)
    assert emitted.data["raw"] == {"x": 0.12, "y": -0.08, "z": 9.6}
    assert emitted.data["source_event"]["producer_id"] == 42
    assert emitted.data["calibration"]["offset"] == pytest.approx([0.12, -0.08, -0.21])
    assert emitted.data["virtual_peripheral"]["name"] == "imu.calibrated"
