"""Regression tests for the regular P0/P1 chain2 HUB75 contract."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    REPO_ROOT
    / "rp1/linux/files/tools/testing/selftests/drivers/rp1-pio/rp1_hub75_run_candidate.sh"
)
REPRO_SCRIPT = REPO_ROOT / "scripts/rp1_hub75_reproduce_totem_blue.sh"
REPRO_DOC = REPO_ROOT / "docs/RP1_HUB75_TOTEM_BLUE_REPRO.md"
SUPERVISOR_SCANNER = REPO_ROOT / "drivers/totem/heart-supervisor-rp1-scanner.sh"
TOTEM_ENV_EXAMPLE = REPO_ROOT / "drivers/totem/totem3.env.example"
RP1H_DRIVER = REPO_ROOT / "rp1/linux/files/drivers/misc/rp1-hub75.c"
REGULAR_PROFILE = (
    REPO_ROOT
    / "rp1/linux/files/tools/testing/selftests/drivers/rp1-pio/"
    "rp1_core1_state32_regular_p0p1_chain2_profile.inc"
)
CLKRETAIN_SCANNER = (
    REPO_ROOT
    / "rp1/linux/files/tools/testing/selftests/drivers/rp1-pio/"
    "rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame6_dwell8_"
    "regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2_clkretain.s"
)
KNOWN_GOOD_CANDIDATE = (
    "state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2"
)
KNOWN_GOOD_PAYLOAD = (
    "rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame6_dwell8_"
    "regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2.bin"
)
KNOWN_GOOD_PWM11_PAYLOAD = (
    "rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame11_dwell8_"
    "regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2.bin"
)
HZELLER_REGULAR_GPIO = {
    "P0_R1": 11,
    "P0_G1": 27,
    "P0_B1": 7,
    "P0_R2": 8,
    "P0_G2": 9,
    "P0_B2": 10,
    "P1_R1": 12,
    "P1_G1": 5,
    "P1_B1": 6,
    "P1_R2": 19,
    "P1_G2": 13,
    "P1_B2": 20,
    "CLK": 17,
    "LAT": 4,
    "OE": 18,
    "A": 22,
    "B": 23,
    "C": 24,
    "D": 25,
    "E": 15,
}


def pin(gpio: int) -> int:
    return 1 << gpio


def test_regular_p0p1_chain2_runner_syntax_accepts_pwm6_oeoffshift_candidate() -> None:
    subprocess.run(["bash", "-n", str(RUNNER)], check=True)

    runner = RUNNER.read_text()

    assert f"{KNOWN_GOOD_CANDIDATE})" in runner
    assert 'case "${RP1_HUB75_PWM_BITS:-11}" in' in runner
    assert "6)" in runner
    assert f'bin="{KNOWN_GOOD_PAYLOAD}"' in runner
    assert "11)" in runner
    assert f'bin="{KNOWN_GOOD_PWM11_PAYLOAD}"' in runner
    assert "set_regular_p0p1_chain2_state32_pwm6_params" in runner
    assert f"{KNOWN_GOOD_CANDIDATE} supports RP1_HUB75_PWM_BITS=6, 8, or 11" in runner


def test_regular_p0p1_chain2_defaults_point_at_oeoffshift_candidate() -> None:
    repro_script = REPRO_SCRIPT.read_text()
    repro_doc = REPRO_DOC.read_text()
    supervisor_scanner = SUPERVISOR_SCANNER.read_text()
    totem_env = TOTEM_ENV_EXAMPLE.read_text()

    assert f'candidate="{KNOWN_GOOD_CANDIDATE}"' in repro_script
    assert KNOWN_GOOD_CANDIDATE in repro_doc
    assert f"HEART_RP1_HUB75_SCANNER_CANDIDATE:-{KNOWN_GOOD_CANDIDATE}" in supervisor_scanner
    assert f"HEART_RP1_HUB75_SCANNER_CANDIDATE={KNOWN_GOOD_CANDIDATE}" in totem_env
    assert "HEART_LAYOUT_COLUMNS=4" in totem_env
    assert "HEART_LAYOUT_ROWS=1" in totem_env
    assert "HEART_RGB_MATRIX_BRIGHTNESS=1.0" in totem_env
    assert "HEART_RGB_MATRIX_BRIGHTNESS_REFERENCE_PWM_BITS=8" in totem_env
    assert "HEART_RGB_MATRIX_GAMMA=cie1931" in totem_env
    assert "HEART_RP1_HUB75_PWM_BITS=11" in totem_env


def test_regular_p0p1_chain2_repro_documents_256x64_abcd_transport_contract() -> None:
    repro_doc = REPRO_DOC.read_text()

    assert "`256x64` RGB888 strip" in repro_doc
    assert "columns as `[A,C]`, then `[B,D]`" in repro_doc
    assert "ordered `A B C D`" in repro_doc
    assert "across x" in repro_doc
    assert "`49152` bytes" in repro_doc


def test_regular_p0p1_chain2_packer_and_wrapper_match_hzeller_regular_gpio() -> None:
    driver = RP1H_DRIVER.read_text()
    profile = REGULAR_PROFILE.read_text()

    for signal, gpio in HZELLER_REGULAR_GPIO.items():
        if signal.startswith("P0_"):
            driver_name = f"RP1H_HZELLER_REGULAR_{signal}"
            profile_name = f"GPIO_{signal[3:]}"
        elif signal.startswith("P1_"):
            driver_name = f"RP1H_REGULAR_{signal}"
            profile_name = f"GPIO_{signal}"
        else:
            driver_name = f"RP1H_HZELLER_REGULAR_{signal}"
            profile_name = f"GPIO_{signal}"

        assert re.search(rf"^#define\s+{driver_name}\s+{gpio}$", driver, re.MULTILINE)
        assert re.search(rf"^\.equ\s+{profile_name},\s+{gpio}$", profile, re.MULTILINE)


def test_clkretain_candidate_disables_frame_end_wrap_prefetch() -> None:
    scanner = CLKRETAIN_SCANNER.read_text()
    profile = REGULAR_PROFILE.read_text()

    assert ".equ REGULAR_P0P1_WRAP_PREFETCH, 0" in scanner
    assert ".equ REGULAR_P0P1_DMA_PIPELINE4, 0" in scanner
    assert ".equ USE_RGB_SETCLR_EXPLICIT_CLKLOW, 1" in scanner
    assert ".equ USE_STATE32_DMA_PIPELINE4_CHUNK_STREAM, 1" in profile
    assert ".equ USE_STATE32_DMA_CHUNK_STREAM, 1" in profile


def test_regular_p0p1_chain2_expected_packer_words_are_exact_gpio_masks() -> None:
    driver = RP1H_DRIVER.read_text()

    oe = pin(HZELLER_REGULAR_GPIO["OE"])
    a_c_transport = (
        oe
        | pin(HZELLER_REGULAR_GPIO["P0_R1"])
        | pin(HZELLER_REGULAR_GPIO["P0_G2"])
        | pin(HZELLER_REGULAR_GPIO["P1_B1"])
        | pin(HZELLER_REGULAR_GPIO["P1_R2"])
    )
    b_d_transport = (
        oe
        | pin(HZELLER_REGULAR_GPIO["P0_G1"])
        | pin(HZELLER_REGULAR_GPIO["P0_B2"])
        | pin(HZELLER_REGULAR_GPIO["P1_R1"])
        | pin(HZELLER_REGULAR_GPIO["P1_G2"])
    )
    row1_a_top_blue = (
        oe | pin(HZELLER_REGULAR_GPIO["A"]) | pin(HZELLER_REGULAR_GPIO["P0_B1"])
    )

    assert oe == 0x00040000
    assert a_c_transport == 0x000c0a40
    assert b_d_transport == 0x08043400
    assert row1_a_top_blue == 0x00440080
    assert "KUNIT_EXPECT_EQ(test, a_c_transport, words[0]);" in driver
    assert "KUNIT_EXPECT_EQ(test, oe, words[1]);" in driver
    assert "KUNIT_EXPECT_EQ(test, b_d_transport, words[64]);" in driver
    assert "words[256]" in driver
