import pytest

from heart.events.types import ForceMeasurement
from heart.peripheral.force import ForcePeripheral


class TestPeripheralForceEvent:
    """Group Peripheral Force Event Bus tests so peripheral force event bus behaviour stays reliable. This preserves confidence in peripheral force event bus for end-to-end scenarios."""

    def test_force_peripheral_emits_event(self) -> None:
        """Verify that force peripheral emits event. This confirms load cell readings reach consumers for haptic feedback."""
        captured = []

        def _capture(event):
            captured.append(event)

        # TODO: Refactor
        # subscribe(ForceMeasurement.EVENT_TYPE, _capture)
        peripheral = ForcePeripheral()

        event = peripheral.record_force(force_type="tensile", magnitude=12.5, unit="N")

        assert captured
        emitted = captured[0]
        assert emitted is event
        assert emitted.event_type == ForceMeasurement.EVENT_TYPE
        assert emitted.data["type"] == "tensile"
        assert emitted.data["magnitude"] == pytest.approx(12.5)
        assert emitted.data["unit"] == "N"



    def test_force_peripheral_normalizes_payload(self) -> None:
        """Verify that force peripheral normalizes payload. This ensures mixed-case inputs still produce canonical telemetry."""
        captured = []

        # subscribe(ForceMeasurement.EVENT_TYPE, captured.append)
        peripheral = ForcePeripheral()

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



    def test_force_peripheral_rejects_invalid_payload(self) -> None:
        """Verify that force peripheral rejects invalid payload. This prevents malformed packets from polluting analytics."""
        captured = []

        # subscribe(ForceMeasurement.EVENT_TYPE, captured.append)
        peripheral = ForcePeripheral()

        peripheral.update_due_to_data({"data": {"force_type": "gravity", "magnitude": 9.81}})

        assert not captured



    def test_force_measurement_validates_type(self) -> None:
        """Verify that force measurement validates type. This protects against unsupported force semantics entering the system."""
        with pytest.raises(ValueError):
            ForceMeasurement(magnitude=1.0, force_type="gravity")
