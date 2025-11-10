"""Integration test ensuring the MQTT sidecar cooperates with the core loop."""

import json
import sys
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable

import pytest

# Ensure the experimental peripheral sidecar package is importable during tests.
EXPERIMENTAL_SRC = (
    Path(__file__).resolve().parents[1] / "experimental" / "peripheral_sidecar" / "src"
)
if str(EXPERIMENTAL_SRC) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTAL_SRC))

from peripheral_sidecar import aggregators as aggregators_module  # noqa: E402
from peripheral_sidecar import mqtt_sidecar  # noqa: E402
from peripheral_sidecar.aggregators import ActionEvent  # noqa: E402
from peripheral_sidecar.aggregators import PeripheralActionMapper  # noqa: E402
from peripheral_sidecar.aggregators import PeripheralPollResult  # noqa: E402
from peripheral_sidecar.aggregators import RawPeripheralSnapshot  # noqa: E402
from peripheral_sidecar.config import PeripheralServiceConfig  # noqa: E402
from peripheral_sidecar.mqtt_sidecar import PeripheralMQTTService  # noqa: E402

from heart.peripheral.core import Peripheral  # noqa: E402


class FakeMQTTBroker:
    """Thread-safe in-memory MQTT broker used for integration testing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: defaultdict[str, list[Callable[[str, str], None]]] = (
            defaultdict(list)
        )
        self.published: defaultdict[str, list[str]] = defaultdict(list)

    def publish(self, topic: str, payload: str) -> None:
        with self._lock:
            self.published[topic].append(payload)
            subscribers = list(self._subscriptions.get(topic, ()))
        for callback in subscribers:
            callback(topic, payload)

    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> None:
        with self._lock:
            self._subscriptions[topic].append(callback)


class FakeMQTTClient:
    """Minimal subset of the paho MQTT client API backed by :class:`FakeMQTTBroker`."""

    def __init__(self, broker: FakeMQTTBroker, client_id: str) -> None:
        self._broker = broker
        self._client_id = client_id
        self._connected = False

    def connect(self, _host: str, _port: int, _keepalive: int) -> None:
        self._connected = True

    def loop_start(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def loop_stop(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: str, qos: int = 0) -> SimpleNamespace:
        self._broker.publish(topic, payload)
        # Match the paho-mqtt return signature where result[0] is the status code.
        return SimpleNamespace(rc=0, mid=0)


class FakePeripheralManager:
    """Peripheral manager that exposes predefined peripherals for the test."""

    def __init__(self, peripherals: Iterable[Peripheral]) -> None:
        self._peripherals = list(peripherals)

    def detect(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def start(self) -> None:  # pragma: no cover - compatibility shim
        return None

    @property
    def peripherals(self) -> tuple[Peripheral, ...]:
        return tuple(self._peripherals)

    def close(self, join_timeout: float = 0.0) -> None:  # pragma: no cover - shim
        return None


@dataclass
class FakeSample:
    timestamp: float
    value: float


class FakeMovingAveragePeripheral(Peripheral):
    """Peripheral that yields predetermined sensor readings."""

    def __init__(self, samples: Iterable[FakeSample]) -> None:
        super().__init__()
        self._samples = deque(samples)
        self._lock = threading.Lock()

    def run(self) -> None:  # pragma: no cover - not used during the test
        raise AssertionError("run should not be invoked in the integration test")

    def pop_sample(self) -> FakeSample | None:
        with self._lock:
            if self._samples:
                return self._samples.popleft()
        return None


class MovingAverageActionMapper(PeripheralActionMapper):
    """Map sensor samples to raw MQTT payloads and moving average actions."""

    def __init__(
        self,
        sensor: FakeMovingAveragePeripheral,
        source: str,
        config: PeripheralServiceConfig,
        window: float = 60.0,
    ) -> None:
        super().__init__(source, config)
        self._sensor = sensor
        self._window = window
        self._history: deque[FakeSample] = deque()

    def poll(self) -> PeripheralPollResult:
        sample = self._sensor.pop_sample()
        if sample is None:
            return PeripheralPollResult.empty()

        self._history.append(sample)
        newest = self._history[-1].timestamp
        cutoff = newest - self._window
        while self._history and self._history[0].timestamp < cutoff:
            self._history.popleft()

        average = sum(item.value for item in self._history) / len(self._history)
        snapshot = RawPeripheralSnapshot(
            source=self.source,
            timestamp=sample.timestamp,
            data={"value": sample.value},
        )
        action = ActionEvent(
            action="sensor.moving_average",
            payload={
                "average": average,
                "count": len(self._history),
                "window_s": self._window,
            },
            source=self.source,
            timestamp=sample.timestamp,
        )
        return PeripheralPollResult(raw_snapshots=[snapshot], action_events=[action])


class TestPeripheralMqttIntegration:
    """Group Peripheral Mqtt Integration tests so peripheral mqtt integration behaviour stays reliable. This preserves confidence in peripheral mqtt integration for end-to-end scenarios."""

    @pytest.mark.timeout(10)
    def test_mqtt_integration_with_moving_average(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """End-to-end verification of raw sensor ingestion and action publication."""

        samples = [
            FakeSample(timestamp=0.0, value=10.0),
            FakeSample(timestamp=30.0, value=20.0),
            FakeSample(timestamp=59.0, value=30.0),
            FakeSample(timestamp=61.0, value=40.0),
        ]
        sensor = FakeMovingAveragePeripheral(samples)
        broker = FakeMQTTBroker()

        monkeypatch.setattr(
            mqtt_sidecar.mqtt,
            "Client",
            lambda client_id: FakeMQTTClient(broker, client_id),
        )

        fake_manager = FakePeripheralManager([sensor])
        monkeypatch.setattr(mqtt_sidecar, "PeripheralManager", lambda: fake_manager)

        original_builder = aggregators_module.build_action_mappers

        def patched_build_action_mappers(
            peripheral: Peripheral, source: str, config: PeripheralServiceConfig
        ):
            if isinstance(peripheral, FakeMovingAveragePeripheral):
                return [MovingAverageActionMapper(peripheral, source, config)]
            return list(original_builder(peripheral, source, config))

        monkeypatch.setattr(
            aggregators_module, "build_action_mappers", patched_build_action_mappers
        )

        raw_messages: list[dict] = []
        action_messages: list[dict] = []
        core_messages: list[dict] = []
        processing_complete = threading.Event()

        def record_raw(_topic: str, payload: str) -> None:
            raw_messages.append(json.loads(payload))

        def record_action(_topic: str, payload: str) -> None:
            parsed = json.loads(payload)
            action_messages.append(parsed)
            core_messages.append(parsed)
            if len(action_messages) == len(samples):
                processing_complete.set()

        config = PeripheralServiceConfig(
            broker_host="localhost",
            broker_port=1883,
            client_id="sidecar-test",
            raw_topic="test/raw",
            action_topic="test/actions",
            poll_interval=0.0,
        )

        broker.subscribe(config.raw_topic, record_raw)
        broker.subscribe(config.action_topic, record_action)

        service = PeripheralMQTTService(config=config)
        service_thread = threading.Thread(target=service.run, daemon=True)
        service_thread.start()

        try:
            assert processing_complete.wait(timeout=5.0), (
                "Timed out waiting for MQTT actions"
            )
        finally:
            service.shutdown()
            service_thread.join(timeout=5.0)

        assert [entry["data"]["value"] for entry in raw_messages] == [
            10.0,
            20.0,
            30.0,
            40.0,
        ]
        assert [entry["action"] for entry in action_messages] == [
            "sensor.moving_average"
        ] * len(samples)

        final_action = action_messages[-1]
        assert final_action["payload"]["count"] == 3
        assert final_action["payload"]["window_s"] == 60.0
        assert final_action["payload"]["average"] == pytest.approx(30.0)
        assert core_messages == action_messages
