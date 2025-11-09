import pytest

from heart.events.types import ForceMeasurement
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.force import ForcePeripheral


def test_force_peripheral_emits_event() -> None:
    bus = EventBus()
    captured = []

    def _capture(event):
        captured.append(event)

    bus.subscribe(ForceMeasurement.EVENT_TYPE, _capture)
    peripheral = ForcePeripheral(event_bus=bus, producer_id=42)

    event = peripheral.record_force(force_type="tensile", magnitude=12.5, unit="N")

    assert captured
    emitted = captured[0]
    assert emitted is event
    assert emitted.event_type == ForceMeasurement.EVENT_TYPE
    assert emitted.data["type"] == "tensile"
    assert emitted.data["magnitude"] == pytest.approx(12.5)
    assert emitted.data["unit"] == "N"
    assert emitted.producer_id == 42


def test_force_peripheral_normalizes_payload() -> None:
    bus = EventBus()
    captured = []

    bus.subscribe(ForceMeasurement.EVENT_TYPE, captured.append)
    peripheral = ForcePeripheral(event_bus=bus, producer_id=7)

    peripheral.update_due_to_data(
        {
            "event_type": ForceMeasurement.EVENT_TYPE,
            "data": {"force_type": "MAGNETIC", "magnitude": "3.5", "unit": "mT"},
        }
    )

    assert captured
    event = captured[0]
    assert event.data["type"] == "magnetic"
    assert event.data["magnitude"] == pytest.approx(3.5)
    assert event.data["unit"] == "mT"
    assert event.producer_id == 7


def test_force_peripheral_rejects_invalid_payload() -> None:
    bus = EventBus()
    captured = []

    bus.subscribe(ForceMeasurement.EVENT_TYPE, captured.append)
    peripheral = ForcePeripheral(event_bus=bus)

    peripheral.update_due_to_data({"data": {"force_type": "gravity", "magnitude": 9.81}})

    assert not captured


def test_force_measurement_validates_type() -> None:
    with pytest.raises(ValueError):
        ForceMeasurement(magnitude=1.0, force_type="gravity")
