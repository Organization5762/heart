from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from manyfold import Graph

from heart.peripheral import heart_rates
from heart.peripheral.heart_rates import (HeartRateManager,
                                          heart_rate_detection_route,
                                          heart_rate_lifecycle_route,
                                          heart_rate_measurement_route)


@dataclass
class _HeartRateDataStub:
    heart_rate: int
    battery_percentage: int | None = None


class _HeartRateDeviceStub:
    device_id = 0x1234


class TestHeartRateManyfoldNode:
    """Cover ANT+ heart-rate discovery and samples as Manyfold-owned graph nodes."""

    def test_detection_node_publishes_heart_rate_manager_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        detected = HeartRateManager()

        def _detect(cls) -> Iterator[HeartRateManager]:
            yield detected

        monkeypatch.setattr(HeartRateManager, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[HeartRateManager] = []

        handle = HeartRateManager.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(heart_rate_detection_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == HeartRateManager.EVENT_DETECTED
        assert latest_detection.value.data == {"source": "ant_plus"}

    def test_detection_node_can_spawn_measurement_source(
        self,
        monkeypatch,
    ) -> None:
        detected = HeartRateManager()

        def _detect(cls) -> Iterator[HeartRateManager]:
            yield detected

        original_install_node = HeartRateManager.install_node

        def _install_node(self: HeartRateManager, graph: Graph, **kwargs):
            kwargs["start_immediately"] = False
            return original_install_node(self, graph, **kwargs)

        def _ant_cycle(self: HeartRateManager) -> None:
            data = _HeartRateDataStub(heart_rate=142, battery_percentage=128)
            self._cb(_HeartRateDeviceStub())(None, None, data)
            self._emit_lifecycle(
                heart_rates.HeartRateLifecycle(
                    status="found",
                    device_id="01234",
                    detail={"device_type": "HeartRate"},
                )
            )
            self._measurement_sink = None
            self._lifecycle_sink = None
            raise KeyboardInterrupt

        monkeypatch.setattr(HeartRateManager, "detect", classmethod(_detect))
        monkeypatch.setattr(HeartRateManager, "install_node", _install_node)
        monkeypatch.setattr(heart_rates, "HeartRateData", _HeartRateDataStub)
        monkeypatch.setattr(HeartRateManager, "_ant_cycle", _ant_cycle)
        graph = Graph()

        handle = HeartRateManager.detection_node(
            start_immediately=False,
            spawn_sources=True,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        try:
            spawned.loop_handle.loop.run(spawned.loop_handle.token)
        except KeyboardInterrupt:
            pass

        latest_measurement = graph.latest(heart_rate_measurement_route())
        latest_lifecycle = graph.latest(heart_rate_lifecycle_route())
        assert latest_measurement is not None
        assert latest_measurement.value.event_type == "peripheral.heart_rate.measurement"
        assert latest_measurement.value.data["device_id"] == "01234"
        assert latest_measurement.value.data["bpm"] == 142
        assert latest_measurement.value.data["battery_level"] == 50.0
        assert latest_lifecycle is not None
        assert latest_lifecycle.value.event_type == "peripheral.heart_rate.lifecycle"
        assert latest_lifecycle.value.data["status"] == "found"
