import pytest

from heart.peripheral import Input
from heart.peripheral.drawing_pad import DrawingPad, StylusSample


def test_defaults_match_spec():
    pad = DrawingPad()
    assert pad.width_inches == pytest.approx(6.0)
    assert pad.height_inches == pytest.approx(6.0)
    assert pad.resolution == 48


def test_apply_stylus_updates_grid_and_history():
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


def test_erase_clears_region():
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


def test_units_in_inches_are_supported():
    pad = DrawingPad(resolution=10)
    pad.apply_stylus(x=3.0, y=3.0, units="inches")

    # 3 inches is the midpoint on a 6 inch pad -> central cell should be non-zero
    sample = pad.last_sample()
    assert sample is not None

    grid = [list(row) for row in pad.iter_rows()]
    x_idx = round(sample.x * (pad.resolution - 1))
    y_idx = round(sample.y * (pad.resolution - 1))
    assert grid[y_idx][x_idx] == pytest.approx(1.0)
