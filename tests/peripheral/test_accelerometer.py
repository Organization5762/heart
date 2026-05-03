from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph
from manyfold.sensor_io import BackoffPolicy, RetryPolicy

from heart.peripheral.sensor import (Accelerometer, FakeAccelerometer,
                                     accelerometer_detection_route,
                                     accelerometer_error_route,
                                     accelerometer_vector_event_route,
                                     magnetometer_vector_event_route)


class _SerialStub:
    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks

    def __enter__(self) -> "_SerialStub":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def readline(self) -> bytes:
        try:
            return next(self._chunks)
        except StopIteration:
            raise KeyboardInterrupt


class TestAccelerometerManyfoldNode:
    """Cover graph-native accelerometer discovery and vector streaming."""

    def test_detection_node_publishes_accelerometer_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        detected = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)

        def _detect(cls) -> Iterator[Accelerometer]:
            yield detected

        monkeypatch.setattr(Accelerometer, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[Accelerometer] = []

        handle = Accelerometer.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(accelerometer_detection_route())
        assert registered == [detected]
        assert latest is not None
        assert latest.value.event_type == "peripheral.accelerometer.detected"
        assert latest.value.data == {"port": "/dev/ttyUSB0", "baudrate": 115200}
        assert latest.value.identity.id == "accelerometer:/dev/ttyUSB0"

    def test_install_node_publishes_vectors_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        peripheral = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)
        payload = b'{"event_type":"sensor.acceleration","data":{"x":1,"y":2,"z":3}}\n'
        monkeypatch.setattr(
            peripheral,
            "_connect_to_ser",
            lambda: _SerialStub(iter((payload,))),
        )
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(accelerometer_vector_event_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.accelerometer.vector"
        assert latest.value.data == {"x": 1.0, "y": 2.0, "z": 3.0}
        assert latest.value.identity.id == "accelerometer:/dev/ttyUSB0"
        assert peripheral.get_acceleration() is not None

    def test_install_node_publishes_magnetometer_vectors_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        peripheral = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)
        payload = b'{"event_type":"sensor.magnetic","data":{"x":7,"y":8,"z":9}}\n'
        monkeypatch.setattr(
            peripheral,
            "_connect_to_ser",
            lambda: _SerialStub(iter((payload,))),
        )
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(magnetometer_vector_event_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.magnetometer.vector"
        assert latest.value.data == {"x": 7.0, "y": 8.0, "z": 9.0}
        assert latest.value.identity.id == "accelerometer:/dev/ttyUSB0"
        assert peripheral.get_acceleration() is None

    def test_detection_node_can_spawn_vector_source(self, monkeypatch) -> None:
        detected = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)
        payload = b'{"event_type":"sensor.acceleration","data":{"x":4,"y":5,"z":6}}\n'

        def _detect(cls) -> Iterator[Accelerometer]:
            yield detected

        monkeypatch.setattr(Accelerometer, "detect", classmethod(_detect))
        monkeypatch.setattr(
            detected,
            "_connect_to_ser",
            lambda: _SerialStub(iter((payload,))),
        )
        graph = Graph()

        handle = Accelerometer.detection_node(
            start_immediately=False,
            spawn_sources=True,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(accelerometer_detection_route())
        latest_vector = graph.latest(accelerometer_vector_event_route())
        assert latest_detection is not None
        assert latest_vector is not None
        assert latest_detection.value.event_type == "peripheral.accelerometer.detected"
        assert latest_vector.value.data == {"x": 4.0, "y": 5.0, "z": 6.0}

    def test_install_node_publishes_exceptions_to_error_route(
        self,
        monkeypatch,
    ) -> None:
        peripheral = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)

        def _connect_to_ser() -> object:
            raise RuntimeError("sensor unavailable")

        monkeypatch.setattr(peripheral, "_connect_to_ser", _connect_to_ser)
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            error_route=accelerometer_error_route(),
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
        )

        try:
            handle.loop_handle.loop.run(handle.loop_handle.token)
        except RuntimeError as exc:
            assert "sensor unavailable" in str(exc)
        else:
            raise AssertionError("expected accelerometer source failure")

        latest = graph.latest(accelerometer_error_route())
        assert latest is not None
        assert isinstance(latest.value, RuntimeError)


class TestFakeAccelerometerManyfoldNode:
    """Cover graph-native fake accelerometer discovery and vector streaming."""

    def test_detection_node_publishes_fake_accelerometer_to_manyfold_route(
        self,
    ) -> None:
        graph = Graph()
        registered: list[FakeAccelerometer] = []

        handle = FakeAccelerometer.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(accelerometer_detection_route())
        assert len(registered) == 1
        assert latest is not None
        assert latest.value.event_type == "peripheral.accelerometer.detected"
        assert latest.value.data == {"mode": "fake"}
        assert latest.value.identity.id == "fake_accelerometer"

    def test_install_node_publishes_fake_vectors_to_manyfold_route(self) -> None:
        peripheral = FakeAccelerometer()
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
            sample_interval_seconds=0,
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(accelerometer_vector_event_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.accelerometer.vector"
        assert 0.0 <= latest.value.data["x"] <= 1.0
        assert 0.0 <= latest.value.data["y"] <= 1.0
        assert latest.value.data["z"] == 9.8
        assert latest.value.identity.id == "fake_accelerometer"
