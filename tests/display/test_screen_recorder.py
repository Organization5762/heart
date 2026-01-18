from dataclasses import dataclass
from pathlib import Path

import pygame
import pytest
from PIL import Image, ImageDraw, ImageSequence

from heart.display.recorder import ScreenRecorder
from heart.display.regression import compare_phash, phash_image
from heart.renderers import StatefulBaseRenderer

HASH_DISTANCE_LIMIT = 16


@dataclass
class SolidColorState:
    color: tuple[int, int, int]


class SolidColorRenderer(StatefulBaseRenderer[SolidColorState]):
    def __init__(self, color: tuple[int, int, int]) -> None:
        super().__init__()
        self._color = color

    def _create_initial_state(
        self, window, clock, peripheral_manager, orientation
    ) -> SolidColorState:
        return SolidColorState(color=self._color)

    def real_process(self, window, clock, orientation) -> None:
        window.fill(self.state.color)


@dataclass
class PatternState:
    background: tuple[int, int, int]
    accent: tuple[int, int, int]


class PatternRenderer(StatefulBaseRenderer[PatternState]):
    def __init__(
        self, background: tuple[int, int, int], accent: tuple[int, int, int]
    ) -> None:
        super().__init__()
        self._background = background
        self._accent = accent

    def _create_initial_state(
        self, window, clock, peripheral_manager, orientation
    ) -> PatternState:
        return PatternState(background=self._background, accent=self._accent)

    def real_process(self, window, clock, orientation) -> None:
        window.fill(self.state.background)
        pygame.draw.rect(window, self.state.accent, pygame.Rect(8, 8, 48, 16))
        pygame.draw.rect(window, self.state.accent, pygame.Rect(16, 40, 32, 16))


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
        colors: list[tuple[int, int, int]],
        screen_recorder: ScreenRecorder,
        tmp_path: Path,
    ) -> None:
        """Verify ScreenRecorder emits a GIF whose frames match renderer colours. This keeps capture fidelity high so visual regressions are caught when renderers change."""
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

    def test_screen_recorder_matches_expected_perceptual_hash(
        self, screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify ScreenRecorder output aligns with a perceptual hash baseline. This guards end-to-end capture against large rendering changes without brittle pixel-by-pixel comparisons."""
        background = (5, 10, 20)
        accent = (220, 40, 60)
        inputs = [[PatternRenderer(background, accent)]]

        result_path = screen_recorder.record(inputs, tmp_path / "hash.gif")

        with Image.open(result_path) as image:
            first_frame = next(ImageSequence.Iterator(image)).convert("RGB")
            observed_hash = phash_image(first_frame)

        expected = Image.new("RGB", (64, 64), background)
        draw = ImageDraw.Draw(expected)
        draw.rectangle([8, 8, 55, 23], fill=accent)
        draw.rectangle([16, 40, 47, 55], fill=accent)
        expected_hash = phash_image(expected)

        distance = observed_hash - expected_hash
        assert (
            distance <= HASH_DISTANCE_LIMIT
        ), f"perceptual hash distance too high: {distance}"

    @pytest.mark.parametrize(
        ("background", "accent"),
        [
            ((12, 24, 48), (200, 30, 80)),
            ((30, 60, 90), (10, 200, 150)),
        ],
    )
    def test_screen_recorder_perceptual_hashes_match_expected_frames(
        self,
        screen_recorder: ScreenRecorder,
        tmp_path: Path,
        background: tuple[int, int, int],
        accent: tuple[int, int, int],
    ) -> None:
        """Verify each captured frame stays close to an expected hash baseline. This keeps multi-frame captures robust against subtle drift while still catching major render changes."""
        inputs = [[PatternRenderer(background, accent)]]
        result_path = screen_recorder.record(inputs, tmp_path / "multi_hash.gif")

        expected = Image.new("RGB", (64, 64), background)
        draw = ImageDraw.Draw(expected)
        draw.rectangle([8, 8, 55, 23], fill=accent)
        draw.rectangle([16, 40, 47, 55], fill=accent)
        expected_hash = phash_image(expected)

        with Image.open(result_path) as image:
            frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(image)]

        assert len(frames) == len(inputs)
        for frame in frames:
            observed_hash = phash_image(frame)
            distance = observed_hash - expected_hash
            assert (
                distance <= HASH_DISTANCE_LIMIT
            ), f"perceptual hash distance too high: {distance}"

    def test_screen_recorder_perceptual_hashes_match_per_frame_baselines(
        self, screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify hash baselines per frame stay close to expected visuals. This protects animated captures from large shifts that would undermine regression coverage."""
        palette = [
            ((5, 10, 20), (220, 40, 60)),
            ((15, 30, 45), (40, 200, 120)),
        ]
        inputs = [[PatternRenderer(background, accent)] for background, accent in palette]
        result_path = screen_recorder.record(inputs, tmp_path / "sequence_hash.gif")

        expected_hashes = []
        for background, accent in palette:
            expected = Image.new("RGB", (64, 64), background)
            draw = ImageDraw.Draw(expected)
            draw.rectangle([8, 8, 55, 23], fill=accent)
            draw.rectangle([16, 40, 47, 55], fill=accent)
            expected_hashes.append(phash_image(expected))

        with Image.open(result_path) as image:
            observed_frames = [
                frame.convert("RGB") for frame in ImageSequence.Iterator(image)
            ]

        assert len(observed_frames) == len(expected_hashes)
        for observed_frame, expected_hash in zip(
            observed_frames, expected_hashes, strict=True
        ):
            observed_hash = phash_image(observed_frame)
            distance = observed_hash - expected_hash
            assert (
                distance <= HASH_DISTANCE_LIMIT
            ), f"perceptual hash distance too high: {distance}"

    def test_screen_recorder_phash_comparison_reports_distance(
        self, screen_recorder: ScreenRecorder
    ) -> None:
        """Verify phash comparison returns a distance with expected bounds. This keeps the regression signal inspectable when reviewing failures."""
        background = (5, 10, 20)
        accent = (220, 40, 60)
        inputs = [[PatternRenderer(background, accent)]]

        frames = screen_recorder.capture_frames(inputs)
        expected = Image.new("RGB", (64, 64), background)
        draw = ImageDraw.Draw(expected)
        draw.rectangle([8, 8, 55, 23], fill=accent)
        draw.rectangle([16, 40, 47, 55], fill=accent)

        comparison = compare_phash(frames[0], expected)

        assert comparison.within(HASH_DISTANCE_LIMIT)
        assert comparison.distance <= HASH_DISTANCE_LIMIT

    def test_screen_recorder_sets_frame_duration(
        self, screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify ScreenRecorder records frames using the expected millisecond duration. This keeps playback timing accurate so exported recordings feel consistent."""
        inputs = [
            [SolidColorRenderer((10, 20, 30))],
            [SolidColorRenderer((30, 40, 50))],
        ]
        result_path = screen_recorder.record(inputs, tmp_path / "duration.gif")

        with Image.open(result_path) as image:
            durations = [
                frame.info.get("duration") for frame in ImageSequence.Iterator(image)
            ]

        expected_duration = max(
            int(round((1000 / screen_recorder.fps) / 10.0) * 10),
            10,
        )
        assert durations == [expected_duration] * len(inputs)

    def test_screen_recorder_requires_inputs(
        self, screen_recorder: ScreenRecorder, tmp_path: Path
    ) -> None:
        """Verify ScreenRecorder raises an error when recording with no renderer frames. This prevents silent failures when capture pipelines are misconfigured."""
        with pytest.raises(ValueError):
            screen_recorder.record([], tmp_path / "empty.gif")
