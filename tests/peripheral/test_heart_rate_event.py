from types import SimpleNamespace

from heart.peripheral.heart_rates import HeartRateManager


class TestPeripheralHeartRateEvent:
    """Group Peripheral Heart Rate Event Bus tests so peripheral heart rate event bus behaviour stays reliable. This preserves confidence in peripheral heart rate event bus for end-to-end scenarios."""

    def test_heart_rate_manager_emits_measurements_and_lifecycle(self):
        """Verify that heart rate manager emits measurements and lifecycle. This ensures event orchestration remains reliable."""
        measurements = []
        lifecycle = []

        # subscribe(HeartRateMeasurement.EVENT_TYPE, measurements.append)
        # subscribe(HeartRateLifecycle.EVENT_TYPE, lifecycle.append)

        manager = HeartRateManager()

        sample = SimpleNamespace(heart_rate=72, battery_percentage=128)

        manager._publish_measurement("0A001", sample)
        manager._mark_disconnect("0A001", suspected=True)

        assert measurements
        measurement = measurements[0]
        assert measurement.data["device_id"] == "0A001"
        assert measurement.data["bpm"] == 72
        assert measurement.producer_id == int("0A001", 16)

        statuses = [event.data["status"] for event in lifecycle]
        assert "connected" in statuses
        assert "suspected_disconnect" in statuses
