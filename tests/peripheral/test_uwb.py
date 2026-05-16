from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from manyfold import Graph
from manyfold.sensor_io import BackoffPolicy, RetryPolicy
from pytest import MonkeyPatch

from heart.peripheral.uwb import (BaseStationMeasurement, FakeUWBPositioning,
                                  LocalizedTarget, uwb_detection_route,
                                  uwb_error_route, uwb_position_event_route)


def _target() -> LocalizedTarget:
    return LocalizedTarget(
        x=1.0,
        y=2.0,
        z=3.0,
        stations=[
            BaseStationMeasurement(
                station_id="bs_0",
                x=0.0,
                y=0.0,
                z=2.5,
                distance=3.5,
            )
        ],
    )


class TestUWBManyfoldNode:
    """Cover graph-native UWB positioning discovery and sample publication."""

    def test_detection_node_publishes_uwb_to_manyfold_route(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        detected = FakeUWBPositioning()

        def _detect(cls) -> Iterator[FakeUWBPositioning]:
            yield detected

        monkeypatch.setattr(FakeUWBPositioning, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[FakeUWBPositioning] = []

        handle = FakeUWBPositioning.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(uwb_detection_route())
        assert registered == [detected]
        assert latest is not None
        assert latest.value.event_type == "peripheral.uwb.detected"
        assert latest.value.data == {
            "base_station_count": len(FakeUWBPositioning.BASE_STATIONS),
            "mode": "fake",
        }
        assert latest.value.identity.id == "fake_uwb_positioning"

    def test_install_node_publishes_positions_to_manyfold_route(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        peripheral = FakeUWBPositioning()
        monkeypatch.setattr(peripheral, "_sample_at_index", lambda _n: _target())
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
            sample_interval_seconds=0,
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(uwb_position_event_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.uwb.position"
        assert latest.value.data == {
            "x": 1.0,
            "y": 2.0,
            "z": 3.0,
            "stations": [
                {
                    "station_id": "bs_0",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 2.5,
                    "distance": 3.5,
                }
            ],
        }
        assert latest.value.identity.id == "fake_uwb_positioning"

    def test_detection_node_can_spawn_position_source(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        detected = FakeUWBPositioning()

        def _detect(cls) -> Iterator[FakeUWBPositioning]:
            yield detected

        def _install_node(
            self: FakeUWBPositioning,
            graph: Graph,
            **kwargs: Any,
        ) -> object:
            graph.publish(
                kwargs["output_route"],
                self._target_to_sensor_event(_target()),
            )
            return object()

        monkeypatch.setattr(FakeUWBPositioning, "detect", classmethod(_detect))
        monkeypatch.setattr(FakeUWBPositioning, "install_node", _install_node)
        graph = Graph()

        handle = FakeUWBPositioning.detection_node(
            start_immediately=False,
            spawn_sources=True,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(uwb_detection_route())
        latest_position = graph.latest(uwb_position_event_route())
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.uwb.detected"
        assert latest_position is not None
        assert latest_position.value.data["stations"][0]["station_id"] == "bs_0"

    def test_install_node_publishes_exceptions_to_error_route(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        peripheral = FakeUWBPositioning()

        def _sample_at_index(_n: int) -> LocalizedTarget:
            raise RuntimeError("uwb unavailable")

        monkeypatch.setattr(peripheral, "_sample_at_index", _sample_at_index)
        graph = Graph()

        handle = peripheral.install_node(
            graph,
            error_route=uwb_error_route(),
            start_immediately=False,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
            sample_interval_seconds=0,
        )

        try:
            handle.loop_handle.loop.run(handle.loop_handle.token)
        except RuntimeError as exc:
            assert "uwb unavailable" in str(exc)
        else:
            raise AssertionError("expected UWB source failure")

        latest = graph.latest(uwb_error_route())
        assert latest is not None
        assert isinstance(latest.value, RuntimeError)
