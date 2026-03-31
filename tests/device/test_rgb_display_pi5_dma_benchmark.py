"""Pi 5 DMA/PIO benchmark integration tests for the clean-room HUB75 runtime."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

RUN_PI5_PIO_TESTS_ENV = "HEART_RUN_PI5_PIO_TESTS"


@pytest.mark.integration
@pytest.mark.slow
class TestRgbDisplayPi5DmaBenchmark:
    """Validate the Pi 5 DMA/PIO benchmark path so transport timings stay reproducible on target hardware."""

    @pytest.mark.parametrize(
        ("chain_length", "expected_packed_bytes"),
        [(1, 32 * 11 * 65), (4, 32 * 11 * 257)],
        ids=["64x64_chain1_pwm11", "64x64_chain4_pwm11"],
    )
    def test_pi5_dma_benchmark_reports_expected_geometry(
        self, chain_length: int, expected_packed_bytes: int
    ) -> None:
        """Verify the Pi 5 DMA benchmark reports the expected packed transport size and non-zero timings. This matters because the benchmark is our repeatable hardware-facing measure before full scanout lands."""

        if os.environ.get(RUN_PI5_PIO_TESTS_ENV) != "1":
            pytest.skip(
                f"Set {RUN_PI5_PIO_TESTS_ENV}=1 to run Pi 5 DMA/PIO integration tests."
            )

        result = subprocess.run(
            [
                "cargo",
                "run",
                "--manifest-path",
                "rust/heart_rust/Cargo.toml",
                "--bin",
                "pi5_pio_bench",
                "--",
                "--panel-rows",
                "64",
                "--panel-cols",
                "64",
                "--chain-length",
                str(chain_length),
                "--parallel",
                "1",
                "--pwm-bits",
                "11",
                "--iterations",
                "1",
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout.strip())

        assert payload["panel_rows"] == 64
        assert payload["panel_cols"] == 64
        assert payload["chain_length"] == chain_length
        assert payload["parallel"] == 1
        assert payload["pwm_bits"] == 11
        assert payload["packed_bytes"] == expected_packed_bytes
        assert payload["pack_mean_ns"] > 0
        assert payload["dma_mean_ns"] > 0
        assert payload["sequential_cycle_mean_ns"] > 0
        assert payload["pipelined_cycle_mean_ns"] > 0
        assert payload["sequential_cycle_hz"] > 0
        assert payload["pipelined_cycle_hz"] > 0
        assert payload["pipeline_speedup"] > 0
        assert payload["transport_only_hz"] > 0
