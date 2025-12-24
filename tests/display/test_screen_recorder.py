from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from heart.display.recorder import ScreenRecorder
from heart.renderers import StatefulBaseRenderer


@dataclass
class SolidColorState:
    color: tuple[int, int, int]


class SolidColorRenderer(StatefulBaseRenderer[SolidColorState]):
    def __init__(self, color: tuple[int, int, int]) -> None:
        super().__init__()
        self._color = color

    def _create_initial_state(self, window, clock, peripheral_manager, orientation) -> SolidColorState:
        return SolidColorState(color=self._color)

    def real_process(self, window, clock, orientation) -> None:
        window.fill(self.state.color)


@pytest.fixture()
def screen_recorder(loop) -> ScreenRecorder:
    return ScreenRecorder(loop, fps=12)


class TestDisplayScreenRecorder:
    """Group Display Screen Recorder tests so display screen recorder behaviour stays reliable. This preserves confidence in display screen recorder for end-to-end scenarios."""

    @pytest.mark.parametrize(
        "colors",
        [
            [(255, 0, 0)],
            [(0, 0, 0), (255, 255, 255), (0, 128, 255)],
        ],
    )
    def test_screen_recorder_writes_expected_frames(
        self,
        colors: list[tuple[int, int, int]], screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify that ScreenRecorder emits a GIF whose frames match the provided renderer colours. This demonstrates capture fidelity so visual regressions are caught when renderers change."""
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
        self,
        screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify that ScreenRecorder records frames using the expected millisecond duration. This keeps playback timing accurate so exported recordings feel consistent."""
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



    def test_screen_recorder_requires_inputs(self, screen_recorder: ScreenRecorder, tmp_path: Path) -> None:
        """Verify that ScreenRecorder raises an error when recording with no renderer frames. This prevents silent failures when capture pipelines are misconfigured."""
        with pytest.raises(ValueError):
            screen_recorder.record([], tmp_path / "empty.gif")
