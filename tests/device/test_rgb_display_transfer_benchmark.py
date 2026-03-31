"""Benchmarks for Python-to-Rust matrix frame submission."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

heart_rust = pytest.importorskip("heart_rust")
if not all(
    hasattr(heart_rust, attribute)
    for attribute in ("ColorOrder", "MatrixConfig", "MatrixDriver", "WiringProfile")
):
    pytest.skip(
        "The installed heart_rust package does not expose the clean-room matrix API.",
        allow_module_level=True,
    )


@dataclass(frozen=True)
class BenchmarkCase:
    label: str
    panel_rows: int
    panel_cols: int
    chain_length: int
    parallel: int
    color_order: object


class TestRgbDisplayTransferBenchmark:
    """Benchmark the Python-to-Rust frame path so transfer overhead stays visible as the clean-room runtime evolves."""

    @pytest.mark.benchmark(group="py_to_rust_matrix_submit_rgba")
    @pytest.mark.parametrize(
        ("case"),
        [
            BenchmarkCase(
                label="32x16_rgb",
                panel_rows=16,
                panel_cols=32,
                chain_length=1,
                parallel=1,
                color_order=heart_rust.ColorOrder.RGB,
            ),
            BenchmarkCase(
                label="64x64_rgb",
                panel_rows=64,
                panel_cols=64,
                chain_length=1,
                parallel=1,
                color_order=heart_rust.ColorOrder.RGB,
            ),
            BenchmarkCase(
                label="128x64_gbr",
                panel_rows=64,
                panel_cols=64,
                chain_length=2,
                parallel=1,
                color_order=heart_rust.ColorOrder.GBR,
            ),
        ],
        ids=lambda case: case.label,
    )
    def test_submit_rgba_python_to_rust_benchmark(
        self, benchmark: pytest.BenchmarkFixture, case: BenchmarkCase
    ) -> None:
        """Benchmark Python-to-Rust `submit_rgba` for representative panel layouts. This matters because the PyO3 bridge must stay cheap enough that frame transfer does not dominate runtime work."""

        config = heart_rust.MatrixConfig(
            wiring=heart_rust.WiringProfile.AdafruitHatPwm,
            panel_rows=case.panel_rows,
            panel_cols=case.panel_cols,
            chain_length=case.chain_length,
            parallel=case.parallel,
            color_order=case.color_order,
        )
        driver = heart_rust.MatrixDriver(config)
        frame = bytes(index % 251 for index in range(driver.width * driver.height * 4))

        def submit_frame() -> None:
            driver.submit_rgba(frame, driver.width, driver.height)

        benchmark(submit_frame)
        driver.close()
