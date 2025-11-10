from __future__ import annotations

from types import SimpleNamespace

import pytest
from helpers.firmware_io import HandlerStep, run_handler_steps

from heart.firmware_io import constants, rotary_encoder


class TestFirmwareIoRotaryEncoderHandler:
    """Group Firmware Io Rotary Encoder Handler tests so firmware io rotary encoder handler behaviour stays reliable. This preserves confidence in firmware io rotary encoder handler for end-to-end scenarios."""

    @pytest.mark.parametrize(
        "index, steps, expected",
        [
            (
                7,
                [
                    HandlerStep("initial"),
                    HandlerStep("rotate-forward", position=4),
                    HandlerStep("steady"),
                ],
                [
                    ("initial", [rotary_encoder.form_json(constants.SWITCH_ROTATION, 0, 7)]),
                    ("rotate-forward", [rotary_encoder.form_json(constants.SWITCH_ROTATION, 4, 7)]),
                    ("steady", []),
                ],
            ),
            (
                5,
                [
                    HandlerStep("initial"),
                    HandlerStep("rotate-negative", position=-3),
                    HandlerStep("repeat", position=-3),
                ],
                [
                    ("initial", [rotary_encoder.form_json(constants.SWITCH_ROTATION, 0, 5)]),
                    ("rotate-negative", [rotary_encoder.form_json(constants.SWITCH_ROTATION, -3, 5)]),
                    ("repeat", []),
                ],
            ),
        ],
    )
    def test_handle_emits_rotation_events_when_position_changes(self, rotary_components, index, steps, expected) -> None:
        """Verify that RotaryEncoderHandler emits rotation events when the encoder position changes. This confirms motion gestures are surfaced for navigation controls."""
        encoder, switch = rotary_components
        handler = rotary_encoder.RotaryEncoderHandler(encoder, switch, index=index)

        timeline = run_handler_steps(handler, encoder, switch, steps)
        assert timeline == expected



    @pytest.mark.parametrize(
        "pull_direction, pressed_value, released_value",
        [
            ("DOWN", True, False),
            ("UP", False, True),
        ],
    )
    def test_handle_emits_button_press_for_press_release_sequence(
        self,
        dummy_pull, deterministic_clock, pull_direction, pressed_value, released_value
    ) -> None:
        """Verify that RotaryEncoderHandler emits a button press when a press-release sequence completes. This links physical button feedback to UI actions relying on taps."""
        encoder = SimpleNamespace(position=12)
        switch = SimpleNamespace(value=released_value, pull=getattr(dummy_pull, pull_direction))
        handler = rotary_encoder.RotaryEncoderHandler(
            encoder, switch, index=2, clock=deterministic_clock.monotonic
        )
        handler.last_position = encoder.position

        steps = [
            HandlerStep("baseline"),
            HandlerStep("press-start", switch_value=pressed_value),
            HandlerStep("press-held", advance=0.2),
            HandlerStep("release", switch_value=released_value, advance=0.1),
        ]

        timeline = run_handler_steps(handler, encoder, switch, steps, clock=deterministic_clock)
        expected_press = rotary_encoder.form_json(constants.BUTTON_PRESS, 1, 2)
        assert timeline == [
            ("baseline", []),
            ("press-start", []),
            ("press-held", []),
            ("release", [expected_press]),
        ]



    @pytest.mark.parametrize(
        "advance_sequence",
        [
            [rotary_encoder.LONG_PRESS_DURATION_SECONDS - 0.1, 0.2, 0.5],
            [rotary_encoder.LONG_PRESS_DURATION_SECONDS, 0.3, 0.0],
        ],
    )
    def test_handle_emits_long_press_once_when_threshold_elapsed(
        self,
        dummy_pull, deterministic_clock, advance_sequence
    ) -> None:
        """Verify that RotaryEncoderHandler only emits a single long-press event after the hold threshold expires. This keeps long-press gestures idempotent so hold-to-trigger actions behave."""
        encoder = SimpleNamespace(position=5)
        switch = SimpleNamespace(value=True, pull=dummy_pull.UP)
        handler = rotary_encoder.RotaryEncoderHandler(
            encoder, switch, index=1, clock=deterministic_clock.monotonic
        )
        handler.last_position = encoder.position

        steps = [
            HandlerStep("baseline"),
            HandlerStep("press-start", switch_value=False),
            HandlerStep("pre-threshold", advance=advance_sequence[0]),
            HandlerStep("long-press", advance=advance_sequence[1]),
            HandlerStep("still-held", advance=advance_sequence[2]),
            HandlerStep("release", switch_value=True),
        ]

        timeline = run_handler_steps(handler, encoder, switch, steps, clock=deterministic_clock)
        expected_long_press = rotary_encoder.form_json(constants.BUTTON_LONG_PRESS, 1, 1)
        labels = [
            "baseline",
            "press-start",
            "pre-threshold",
            "long-press",
            "still-held",
            "release",
        ]
        expected_timeline = [(label, []) for label in labels]
        threshold = rotary_encoder.LONG_PRESS_DURATION_SECONDS
        long_press_index = 2 if advance_sequence[0] >= threshold else 3
        expected_timeline[long_press_index] = (
            expected_timeline[long_press_index][0],
            [expected_long_press],
        )

        assert timeline == expected_timeline
        assert handler.press_started_timestamp is None
        assert handler.long_pressed_sent is False



    def test_seesaw_streams_events_from_all_handlers(self, rotary_components) -> None:
        """Verify that Seesaw aggregates events from each registered handler. This demonstrates integration across attachments so multi-knob rigs stay synchronized."""
        encoder, switch = rotary_components
        handler_a = rotary_encoder.RotaryEncoderHandler(encoder, switch, index=3)
        handler_b = rotary_encoder.RotaryEncoderHandler(encoder, switch, index=4)

        seesaw = rotary_encoder.Seesaw([handler_a, handler_b])

        events = list(seesaw.handle())
        expected = [
            rotary_encoder.form_json(constants.SWITCH_ROTATION, 0, 3),
            rotary_encoder.form_json(constants.SWITCH_ROTATION, 0, 4),
        ]
        assert events == expected
