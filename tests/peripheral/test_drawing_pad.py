import time

import pytest
from manyfold import Graph

from heart.peripheral.core import Input
from heart.peripheral.drawing_pad import (DrawingPad, StylusSample,
                                          drawing_pad_detection_route,
                                          drawing_pad_sample_event_route)


class TestPeripheralDrawingPad:
    """Group Peripheral Drawing Pad tests so peripheral drawing pad behaviour stays reliable. This preserves confidence in peripheral drawing pad for end-to-end scenarios."""

    def test_defaults_match_spec(self):
        """Verify that DrawingPad initialises with the documented dimensions and resolution. This keeps firmware assumptions in sync with the physical pad."""
        pad = DrawingPad()
        assert pad.width_inches == pytest.approx(6.0)
        assert pad.height_inches == pytest.approx(6.0)
        assert pad.resolution == 48

    def test_apply_stylus_updates_grid_and_history(self):
        """Verify that DrawingPad.handle_input records stylus samples and updates the grid pressures. This ensures strokes appear on the canvas for creative tools."""
        pad = DrawingPad(resolution=8)

        pad.handle_input(
            Input(
                event_type="drawing_pad.stroke",
                data={"x": 0.5, "y": 0.5, "pressure": 0.8, "radius": 0.2},
            )
        )

        sample = pad.last_sample()
        assert isinstance(sample, StylusSample)
        assert not sample.is_erase
        assert sample.pressure == pytest.approx(0.8)

        # The centre cell should be filled with the provided pressure value.
        grid = [list(row) for row in pad.iter_rows()]
        centre_index = pad.resolution // 2
        assert grid[centre_index][centre_index] == pytest.approx(0.8)

    def test_erase_clears_region(self):
        """Verify that DrawingPad processes erase events by clearing the affected cells. This keeps undo gestures from leaving artifacts on the grid."""
        pad = DrawingPad(resolution=8)
        pad.apply_stylus(x=0.5, y=0.5, pressure=1.0, radius=0.3)

        pad.handle_input(
            Input(
                event_type="drawing_pad.erase", data={"x": 0.5, "y": 0.5, "radius": 0.3}
            )
        )

        sample = pad.last_sample()
        assert sample is not None and sample.is_erase

        for row in pad.iter_rows():
            for value in row:
                assert value == pytest.approx(0.0)

    def test_units_in_inches_are_supported(self):
        """Verify that DrawingPad accepts stylus coordinates expressed in inches. This supports hardware that emits real-world measurements instead of normalized coordinates."""
        pad = DrawingPad(resolution=10)
        pad.apply_stylus(x=3.0, y=3.0, units="inches")

        # 3 inches is the midpoint on a 6 inch pad -> central cell should be non-zero
        sample = pad.last_sample()
        assert sample is not None

        grid = [list(row) for row in pad.iter_rows()]
        x_idx = round(sample.x * (pad.resolution - 1))
        y_idx = round(sample.y * (pad.resolution - 1))
        assert grid[y_idx][x_idx] == pytest.approx(1.0)


class TestDrawingPadManyfoldRuntime:
    """Cover graph-native drawing pad discovery and stylus sample publication."""

    def test_detection_node_publishes_drawing_pad_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        detected = DrawingPad(resolution=12)

        def _detect(cls):
            yield detected

        monkeypatch.setattr(DrawingPad, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[DrawingPad] = []

        handle = DrawingPad.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(drawing_pad_detection_route())
        assert registered == [detected]
        assert latest is not None
        assert latest.value.event_type == "peripheral.drawing_pad.detected"
        assert latest.value.data == {
            "width_inches": 6.0,
            "height_inches": 6.0,
            "resolution": 12,
        }
        assert latest.value.identity.id == "drawing_pad"

    def test_install_node_publishes_stylus_samples_to_manyfold_route(self) -> None:
        pad = DrawingPad(resolution=8, polling_interval=0.01)
        graph = Graph()

        handle = pad.install_node(graph)
        try:
            deadline = time.monotonic() + 1.0
            while not pad._sample_publishers and time.monotonic() < deadline:
                time.sleep(0.01)
            assert pad._sample_publishers

            pad.handle_input(
                Input(
                    event_type="drawing_pad.stroke",
                    data={"x": 0.25, "y": 0.5, "pressure": 0.7, "radius": 0.1},
                )
            )
        finally:
            handle.dispose(timeout=1.0)

        latest = graph.latest(drawing_pad_sample_event_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.drawing_pad.sample"
        assert latest.value.data == {
            "x": 0.25,
            "y": 0.5,
            "pressure": 0.7,
            "radius": 0.1,
            "is_erase": False,
        }
        assert latest.value.identity.id == "drawing_pad"
