"""Pi 5 pinctrl-backed debug tests for the clean-room HUB75 runtime."""

from __future__ import annotations

import os

import pytest

from heart.device.rgb_display.debug import (PI5_HAT_PWM_BACKEND_NAME,
                                            run_pi5_pinctrl_debug_probe)

RUN_PI5_PINCTRL_TESTS_ENV = "HEART_RUN_PI5_PINCTRL_TESTS"
EXPECTED_DRIVEN_STATE_SUBSTRINGS = {
    5: ("op", "dh", "pn", "hi"),
    6: ("op", "dh", "pn", "hi"),
    12: ("op", "dl", "pn", "lo"),
    13: ("op", "dl", "pn", "lo"),
    16: ("op", "dh", "pn", "hi"),
    17: ("op", "dl", "pn", "lo"),
    18: ("op", "dh", "pn", "hi"),
    20: ("op", "dh", "pn", "hi"),
    21: ("op", "dh", "pn", "hi"),
    22: ("op", "dl", "pn", "lo"),
    23: ("op", "dl", "pn", "lo"),
    24: ("op", "dh", "pn", "hi"),
    26: ("op", "dh", "pn", "hi"),
    27: ("op", "dl", "pn", "lo"),
}


@pytest.mark.integration
@pytest.mark.slow
class TestRgbDisplayPinctrlDebug:
    """Validate the Pi 5 pinctrl debug probe so the clean-room HUB75 runtime can expose real GPIO state before panel hardware is attached."""

    @pytest.mark.parametrize(
        ("panel_rows", "panel_cols", "chain_length", "parallel"),
        [(64, 64, 1, 1)],
        ids=["64x64_single_panel"],
    )
    def test_pi5_pinctrl_debug_probe_drives_expected_gpio_pattern(
        self, panel_rows: int, panel_cols: int, chain_length: int, parallel: int
    ) -> None:
        """Verify the Pi 5 debug probe drives and restores the expected 64x64 HUB75 GPIO pattern. This matters because it gives a hardware-visible integration check before a panel is connected."""

        if os.environ.get(RUN_PI5_PINCTRL_TESTS_ENV) != "1":
            pytest.skip(
                f"Set {RUN_PI5_PINCTRL_TESTS_ENV}=1 to run Pi 5 pinctrl integration tests."
            )

        snapshot = run_pi5_pinctrl_debug_probe(
            panel_rows=panel_rows,
            panel_cols=panel_cols,
            chain_length=chain_length,
            parallel=parallel,
        )

        assert snapshot.backend_name == PI5_HAT_PWM_BACKEND_NAME
        assert snapshot.width == panel_cols * chain_length
        assert snapshot.height == panel_rows * parallel
        assert snapshot.pin_states_before.keys() == EXPECTED_DRIVEN_STATE_SUBSTRINGS.keys()
        assert snapshot.pin_states_driven.keys() == EXPECTED_DRIVEN_STATE_SUBSTRINGS.keys()
        assert snapshot.pin_states_restored.keys() == EXPECTED_DRIVEN_STATE_SUBSTRINGS.keys()
        for gpio, expected_tokens in EXPECTED_DRIVEN_STATE_SUBSTRINGS.items():
            driven_state = snapshot.pin_states_driven[gpio]
            restored_state = snapshot.pin_states_restored[gpio]
            assert all(
                token in driven_state for token in expected_tokens
            ), f"GPIO{gpio} did not expose the expected driven state: {driven_state}"
            assert " = none" in restored_state, (
                f"GPIO{gpio} did not restore to NONE after the debug probe: {restored_state}"
            )
