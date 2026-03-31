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
        """Verify the Pi 5 full-scan benchmark reports the expected four-panel geometry and non-zero timings. This matters because the kernel-resident replay path is only useful if the target 64x64 x4 configuration stays benchmarkable on the Pi."""

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
                "4",
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
        assert payload["chain_length"] == 4
        assert payload["parallel"] == 1
        assert payload["pwm_bits"] == 11
        assert 0 < payload["word_count"] <= 32 * 11 * (256 + 5)
        assert payload["compressed_blank_groups"] >= 32 * 3
        assert payload["merged_identical_groups"] >= 0
        assert payload["pack_mean_ns"] > 0
        assert payload["stream_mean_ns"] > 0
        assert payload["resident_backend"] == "kernel_loop"
        assert payload["resident_loop_ms"] == 100
        assert payload["resident_first_render_ns"] > 0
        assert payload["resident_steady_window_ns"] > 0
        assert payload["resident_refresh_count"] >= 0
        assert payload["resident_refresh_hz"] > 0
        assert payload["distinct_frame_update_cycle_mean_ns"] > 0
        assert payload["distinct_frame_update_hz"] > 0
        assert payload["sequential_cycle_mean_ns"] > 0
        assert payload["sequential_cycle_hz"] > 0
