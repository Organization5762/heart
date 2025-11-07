from types import SimpleNamespace

from heart.events.types import HeartRateLifecycle, HeartRateMeasurement
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.heart_rates import HeartRateManager


def test_heart_rate_manager_emits_measurements_and_lifecycle():
    bus = EventBus()
    measurements = []
    lifecycle = []

    bus.subscribe(HeartRateMeasurement.EVENT_TYPE, measurements.append)
    bus.subscribe(HeartRateLifecycle.EVENT_TYPE, lifecycle.append)

    manager = HeartRateManager(event_bus=bus)

    sample = SimpleNamespace(heart_rate=72, battery_percentage=128)

    manager._mark_connected("0A001")
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
