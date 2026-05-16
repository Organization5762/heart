from __future__ import annotations

import time
from collections.abc import Iterator

from manyfold import Graph
from manyfold.sensor_io import BackoffPolicy, RetryPolicy, SensorEvent

from heart.peripheral.compass import (Compass, compass_detection_route,
                                      compass_heading_event_route,
                                      compass_vector_event_route)
from heart.peripheral.sensor import magnetometer_vector_event_route


class TestCompassManyfoldNode:
    """Cover graph-native compass detection and magnetometer transforms."""

    def test_handle_input_updates_vector_and_heading(self) -> None:
        compass = Compass()

        compass.update_due_to_data(
            {
                "event_type": "peripheral.magnetometer.vector",
                "data": {"x": 1, "y": 0, "z": 0},
            }
        )

        assert compass.get_latest_vector() == (1.0, 0.0, 0.0)
        assert compass.get_heading_degrees() == 90.0

    def test_detection_node_publishes_compass_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        detected = Compass(window_size=3)

        def _detect(cls) -> Iterator[Compass]:
            yield detected

        monkeypatch.setattr(Compass, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[Compass] = []

        handle = Compass.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(compass_detection_route())
        assert registered == [detected]
        assert latest is not None
        assert latest.value.event_type == "peripheral.compass.detected"
        assert latest.value.data == {"window_size": 3}
        assert latest.value.identity.id == "compass:magnetometer"

    def test_install_node_publishes_compass_state_from_magnetometer_route(
        self,
    ) -> None:
        compass = Compass()
        graph = Graph()

        handle = compass.install_node(
            graph,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
        )
        try:
            graph.publish(
                magnetometer_vector_event_route(),
                SensorEvent(
                    event_type="peripheral.magnetometer.vector",
                    data={"x": 0.0, "y": 1.0, "z": 2.0},
                    observed_at=1.0,
                ),
            )

            latest_vector = graph.latest(compass_vector_event_route())
            latest_heading = graph.latest(compass_heading_event_route())
            assert latest_vector is not None
            assert latest_vector.value.event_type == "peripheral.compass.vector"
            assert latest_vector.value.data == {"x": 0.0, "y": 1.0, "z": 2.0}
            assert latest_vector.value.identity.id == "compass:magnetometer"
            assert latest_heading is not None
            assert latest_heading.value.event_type == "peripheral.compass.heading"
            assert latest_heading.value.data == {"degrees": 0.0}
        finally:
            handle.dispose(timeout=1.0)

    def test_detection_node_can_spawn_compass_source(self, monkeypatch) -> None:
        detected = Compass()

        def _detect(cls) -> Iterator[Compass]:
            yield detected

        monkeypatch.setattr(Compass, "detect", classmethod(_detect))
        graph = Graph()

        handle = Compass.detection_node(spawn_sources=True).install(graph)
        try:
            handle.node_handle.join()
            assert len(handle.spawned_handles) == 1

            graph.publish(
                magnetometer_vector_event_route(),
                SensorEvent(
                    event_type="peripheral.magnetometer.vector",
                    data={"x": 1.0, "y": 0.0, "z": 0.0},
                    observed_at=1.0,
                ),
            )

            latest_vector = None
            for _ in range(20):
                latest_vector = graph.latest(compass_vector_event_route())
                if latest_vector is not None:
                    break
                time.sleep(0.01)

            assert latest_vector is not None
            assert latest_vector.value.data == {"x": 1.0, "y": 0.0, "z": 0.0}
        finally:
            handle.dispose(timeout=1.0)
