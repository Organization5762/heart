import pytest

from heart.peripheral.core import Input
from heart.peripheral.drawing_pad import DrawingPad, StylusSample


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
            Input(event_type="drawing_pad.erase", data={"x": 0.5, "y": 0.5, "radius": 0.3})
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
