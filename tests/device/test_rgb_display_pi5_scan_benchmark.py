"""Pi 5 full-scan benchmark integration tests for the clean-room HUB75 runtime."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

RUN_PI5_SCAN_TESTS_ENV = "HEART_RUN_PI5_SCAN_TESTS"


@pytest.mark.integration
@pytest.mark.slow
class TestRgbDisplayPi5ScanBenchmark:
    """Validate the Pi 5 full-scan benchmark path so real scanout timings stay inspectable on target hardware."""

    def test_pi5_scan_benchmark_reports_expected_geometry(self) -> None:
        """Verify the Pi 5 full-scan benchmark reports the expected geometry and non-zero timings. This matters because the production backend now depends on the scan scheduler rather than raw DMA transport alone."""

        if os.environ.get(RUN_PI5_SCAN_TESTS_ENV) != "1":
            pytest.skip(
                f"Set {RUN_PI5_SCAN_TESTS_ENV}=1 to run Pi 5 full-scan integration tests."
            )

        result = subprocess.run(
            [
                "cargo",
                "run",
                "--release",
                "--manifest-path",
                "rust/heart_rust/Cargo.toml",
                "--bin",
                "pi5_scan_bench",
                "--",
                "--panel-rows",
                "64",
                "--panel-cols",
                "64",
                "--chain-length",
                "1",
                "--parallel",
                "1",
                "--iterations",
                "1",
                "--frame-count",
                "8",
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout.strip())

        assert payload["panel_rows"] == 64
        assert payload["panel_cols"] == 64
        assert payload["chain_length"] == 1
        assert payload["parallel"] == 1
        assert payload["pwm_bits"] == 11
        assert payload["word_count"] == 32 * 11 * (64 + 11)
        assert payload["pack_mean_ns"] > 0
        assert payload["stream_mean_ns"] > 0
        assert payload["sequential_cycle_mean_ns"] > 0
        assert payload["pipelined_cycle_mean_ns"] > 0
        assert payload["sequential_cycle_hz"] > 0
        assert payload["pipelined_cycle_hz"] > 0
        assert payload["pipeline_speedup"] > 0
