import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest
from PIL import Image, ImageSequence

from heart.display.recorder import ScreenRecorder
from heart.display.renderers import BaseRenderer


class SolidColorRenderer(BaseRenderer):
    def __init__(self, color: tuple[int, int, int]) -> None:
        super().__init__()
        self._color = color

    def process(self, window, clock, peripheral_manager, orientation) -> None:
        window.fill(self._color)


@pytest.fixture()
def screen_recorder(loop) -> ScreenRecorder:
    return ScreenRecorder(loop, fps=12)


@pytest.mark.parametrize(
    "colors",
    [
        [(255, 0, 0)],
        [(0, 0, 0), (255, 255, 255), (0, 128, 255)],
    ],
)
def test_screen_recorder_writes_expected_frames(
    colors: list[tuple[int, int, int]], screen_recorder: ScreenRecorder, tmp_path: Path
) -> None:
    inputs = [[SolidColorRenderer(color)] for color in colors]

    output_path = tmp_path / "capture.gif"
    result_path = screen_recorder.record(inputs, output_path)

    assert result_path.exists()

    with Image.open(result_path) as image:
        observed = [
            frame.convert("RGB").getpixel((0, 0))
            for frame in ImageSequence.Iterator(image)
        ]

    assert observed == colors


def test_screen_recorder_sets_frame_duration(
    screen_recorder: ScreenRecorder, tmp_path: Path
) -> None:
    inputs = [
        [SolidColorRenderer((10, 20, 30))],
        [SolidColorRenderer((30, 40, 50))],
    ]
    result_path = screen_recorder.record(inputs, tmp_path / "duration.gif")

    with Image.open(result_path) as image:
        durations = [
            frame.info.get("duration")
            for frame in ImageSequence.Iterator(image)
        ]

    expected_duration = max(
        int(round((1000 / screen_recorder.fps) / 10.0) * 10),
        10,
    )
    assert durations == [expected_duration] * len(inputs)


def test_screen_recorder_requires_inputs(screen_recorder: ScreenRecorder, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        screen_recorder.record([], tmp_path / "empty.gif")
